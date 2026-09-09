# ============================================================
# MoodBeats Music Knowledge Base Builder (Enhanced)
# ============================================================
# Run in Kaggle with "Spotify Tracks Dataset" by Maharshi Pandya
# https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset
#
# Pipeline:
#   1.  Load 114K+ Spotify tracks
#   2.  Hardened feature engineering (clipped ratios, log transforms, interactions)
#   3.  Compute per-feature statistics
#   4.  Build dynamic genre audio profiles
#   5.  Genre clustering with multi-metric evaluation
#   6.  Deep Autoencoder (residual skip connections, cosine LR, train/val split)
#       - Optional VAE mode for smoother latent geometry
#   7.  GMM soft clustering on latent space (BIC + silhouette + CH + DB)
#   8.  Russell's Circumplex auto-labeling (valence-arousal quadrant mapping)
#   9.  UMAP latent space visualization (mood + genre colored)
#   10. Mood x genre probability matrix
#   11. Musical key and mode analysis
#   12. Tempo zone analysis
#   13. Genre cosine similarity matrix
#   14. Artist-level mood fingerprints
#   15. Mood transition probability matrix
#   16. Build enriched knowledge base JSON
#   17. Summary and file manifest
# ============================================================

import pandas as pd
import numpy as np
import json
import os
import warnings
from collections import Counter

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm

warnings.filterwarnings('ignore')

# ===== CONFIGURATION ======================================
USE_VAE = False
LATENT_DIM = 12
BATCH_SIZE = 1024
EPOCHS = 100
LEARNING_RATE = 1e-3
VAL_SPLIT = 0.1
MIN_ARTIST_TRACKS = 5
UMAP_SAMPLE_SIZE = 30000
CLUSTER_K_RANGE = (6, 20)
SEED = 42
# ===========================================================

np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


# ===== UTILITY FUNCTIONS ===================================

def safe_ratio(numerator, denominator, clip_max=10.0):
    result = numerator / (denominator + 1e-6)
    return np.clip(result, 0.0, clip_max)


def log_transform(series):
    return np.log1p(np.clip(series, 0.0, None))


def compute_r_squared(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2, axis=0)
    ss_tot = np.sum((y_true - np.mean(y_true, axis=0)) ** 2, axis=0)
    return 1.0 - (ss_res / np.clip(ss_tot, 1e-9, None))


# ===== MODEL ARCHITECTURES =================================

class ResidualBlock(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.GELU(),
            nn.Dropout(0.15),
        )

    def forward(self, x):
        return x + self.block(x)


class SongAutoencoder(nn.Module):
    def __init__(self, input_dim, latent_dim):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.BatchNorm1d(64),
            nn.GELU(),
            nn.Dropout(0.2),
            ResidualBlock(64),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.GELU(),
            nn.Dropout(0.15),
            ResidualBlock(32),
            nn.Linear(32, latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 32),
            nn.BatchNorm1d(32),
            nn.GELU(),
            nn.Dropout(0.15),
            ResidualBlock(32),
            nn.Linear(32, 64),
            nn.BatchNorm1d(64),
            nn.GELU(),
            nn.Dropout(0.15),
            ResidualBlock(64),
            nn.Linear(64, input_dim),
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z), z

    def encode(self, x):
        return self.encoder(x)


class SongVAE(nn.Module):
    def __init__(self, input_dim, latent_dim):
        super().__init__()
        self.encoder_shared = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.BatchNorm1d(64),
            nn.GELU(),
            nn.Dropout(0.2),
            ResidualBlock(64),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.GELU(),
            nn.Dropout(0.15),
            ResidualBlock(32),
        )
        self.fc_mu = nn.Linear(32, latent_dim)
        self.fc_logvar = nn.Linear(32, latent_dim)
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 32),
            nn.BatchNorm1d(32),
            nn.GELU(),
            nn.Dropout(0.15),
            ResidualBlock(32),
            nn.Linear(32, 64),
            nn.BatchNorm1d(64),
            nn.GELU(),
            nn.Dropout(0.15),
            ResidualBlock(64),
            nn.Linear(64, input_dim),
        )

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def forward(self, x):
        h = self.encoder_shared(x)
        mu = self.fc_mu(h)
        logvar = self.fc_logvar(h)
        z = self.reparameterize(mu, logvar)
        recon = self.decoder(z)
        return recon, mu, logvar, z

    def encode(self, x):
        h = self.encoder_shared(x)
        return self.fc_mu(h)


# ===== RUSSELL'S CIRCUMPLEX AUTO-LABELING ==================

CIRCUMPLEX_QUADRANTS = {
    (True, True):   ['euphoric', 'exhilarated', 'thrilled'],
    (True, False):  ['serene', 'peaceful', 'calm'],
    (False, True):  ['intense', 'turbulent', 'aggressive'],
    (False, False): ['melancholic', 'somber', 'reflective'],
}

SECONDARY_MODIFIERS = [
    ('danceability', 'groovy'),
    ('acousticness', 'acoustic'),
    ('instrumentalness', 'ambient'),
    ('speechiness', 'vocal'),
    ('tempo_norm', 'driving'),
]


def circumplex_label(centroid_original, mood_features, global_medians, used_labels):
    feat_vals = {f: centroid_original[i] for i, f in enumerate(mood_features)}
    feat_meds = global_medians

    valence_val = feat_vals.get('valence', 0.5)
    energy_val = feat_vals.get('energy', 0.5)
    valence_med = feat_meds.get('valence', 0.5)
    energy_med = feat_meds.get('energy', 0.5)

    high_valence = valence_val > valence_med
    high_energy = energy_val > energy_med
    quadrant_key = (high_valence, high_energy)

    valence_strength = abs(valence_val - valence_med)
    energy_strength = abs(energy_val - energy_med)
    quadrant_intensity = valence_strength + energy_strength

    candidates = CIRCUMPLEX_QUADRANTS[quadrant_key]

    if quadrant_intensity > 0.15:
        base = candidates[0]
    elif quadrant_intensity > 0.05:
        base = candidates[1]
    else:
        base = candidates[2]

    best_modifier = None
    best_deviation = 0.0
    for feat_name, mod_name in SECONDARY_MODIFIERS:
        if feat_name in feat_vals and feat_name in feat_meds:
            dev = feat_vals[feat_name] - feat_meds[feat_name]
            if dev > best_deviation:
                best_deviation = dev
                best_modifier = mod_name

    if best_modifier and best_deviation > 0.05:
        label = f"{base}_{best_modifier}"
    else:
        label = base

    if label in used_labels:
        suffix = 2
        while f"{label}_{suffix}" in used_labels:
            suffix += 1
        label = f"{label}_{suffix}"

    return label


# ===== PIPELINE START ======================================

print("=" * 70)
print("MOODBEATS KNOWLEDGE BASE BUILDER (Enhanced)")
print(f"Mode: {'VAE' if USE_VAE else 'Autoencoder'} | Latent: {LATENT_DIM} | Device: {device}")
print("=" * 70)

# -- STEP 1: LOAD & INSPECT --------------------------------
print("\n" + "=" * 70)
print("STEP 1: Loading dataset")
print("=" * 70)

csv_path = '/kaggle/input/-spotify-tracks-dataset/dataset.csv'
if not os.path.exists(csv_path):
    csv_path = '/kaggle/input/spotify-tracks-dataset/dataset.csv'
if not os.path.exists(csv_path):
    import glob
    candidates = glob.glob('/kaggle/input/**/dataset.csv', recursive=True)
    csv_path = candidates[0] if candidates else csv_path

df = pd.read_csv(csv_path)
print(f"Loaded {len(df):,} tracks")
print(f"Columns ({len(df.columns)}): {list(df.columns)}")
print(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")

exclude_cols = ['Unnamed: 0', 'track_id', 'popularity', 'duration_ms', 'explicit', 'time_signature']
feature_cols = [c for c in df.columns if df[c].dtype in ['float64', 'int64'] and c not in exclude_cols]
print(f"Audio features detected ({len(feature_cols)}): {feature_cols}")

genre_col = 'track_genre' if 'track_genre' in df.columns else 'genre' if 'genre' in df.columns else None
if genre_col is None:
    str_cols = df.select_dtypes(include='object').columns
    genre_col = max(str_cols, key=lambda c: df[c].nunique()) if len(str_cols) > 0 else None

genres = sorted(df[genre_col].unique()) if genre_col else []
print(f"Genre column: '{genre_col}' ({len(genres)} unique genres)")

null_counts = df[feature_cols].isnull().sum()
if null_counts.any():
    print(f"Null values detected: {dict(null_counts[null_counts > 0])}")
    df[feature_cols] = df[feature_cols].fillna(df[feature_cols].median())
    print("Filled nulls with column medians")

# -- STEP 2: HARDENED FEATURE ENGINEERING -------------------
print("\n" + "=" * 70)
print("STEP 2: Feature engineering (hardened ratios, log transforms, interactions)")
print("=" * 70)

base_mood_features = [f for f in ['energy', 'valence', 'danceability', 'acousticness',
                                   'instrumentalness', 'speechiness', 'tempo']
                      if f in feature_cols]

df['energy_acoustic_ratio'] = safe_ratio(df['energy'], df['acousticness'])
df['valence_energy_ratio'] = safe_ratio(df['valence'], df['energy'])
df['dance_energy_ratio'] = safe_ratio(df['danceability'], df['energy'])
df['speech_instrumental_ratio'] = safe_ratio(df['speechiness'], df['instrumentalness'])

df['mood_intensity'] = df['energy'] * df['valence']
df['acoustic_depth'] = df['acousticness'] * (1.0 - df['energy'])
df['vocal_energy'] = (1.0 - df['instrumentalness']) * df['energy']
df['groove_factor'] = df['danceability'] * df['energy'] * df['valence']

if 'tempo' in df.columns:
    tempo_max = df['tempo'].max()
    df['tempo_norm'] = df['tempo'] / tempo_max if tempo_max > 0 else 0.0

if 'duration_ms' in df.columns:
    df['duration_min'] = df['duration_ms'] / 60000.0

if 'loudness' in df.columns:
    df['loudness_norm'] = (df['loudness'] - df['loudness'].min()) / (df['loudness'].max() - df['loudness'].min() + 1e-9)

df['log_speechiness'] = log_transform(df['speechiness']) if 'speechiness' in df.columns else 0.0
df['log_instrumentalness'] = log_transform(df['instrumentalness']) if 'instrumentalness' in df.columns else 0.0
df['log_liveness'] = log_transform(df['liveness']) if 'liveness' in df.columns else 0.0

ratio_features = ['energy_acoustic_ratio', 'valence_energy_ratio', 'dance_energy_ratio',
                   'speech_instrumental_ratio']
interaction_features = ['mood_intensity', 'acoustic_depth', 'vocal_energy', 'groove_factor']
normalized_features = [f for f in ['tempo_norm', 'duration_min', 'loudness_norm'] if f in df.columns]
log_features = [f for f in ['log_speechiness', 'log_instrumentalness', 'log_liveness'] if f in df.columns]

mood_features = [f for f in base_mood_features + ratio_features + interaction_features
                 + normalized_features + log_features if f in df.columns]

print(f"Base features     ({len(base_mood_features)}): {base_mood_features}")
print(f"Ratio features    ({len(ratio_features)}):  {ratio_features}")
print(f"Interaction feat  ({len(interaction_features)}):  {interaction_features}")
print(f"Normalized feat   ({len(normalized_features)}):  {normalized_features}")
print(f"Log features      ({len(log_features)}):  {log_features}")
print(f"TOTAL mood features ({len(mood_features)})")

skewness = df[mood_features].skew()
high_skew = skewness[skewness.abs() > 2.0]
if len(high_skew) > 0:
    print(f"High-skewness features (|skew| > 2.0): {dict(high_skew.round(2))}")

# -- STEP 3: COMPUTE FEATURE STATISTICS --------------------
print("\n" + "=" * 70)
print("STEP 3: Computing feature statistics")
print("=" * 70)

feature_stats = {}
for col in feature_cols:
    vals = df[col].dropna()
    feature_stats[col] = {
        'mean': float(vals.mean()),
        'std': float(vals.std()),
        'min': float(vals.min()),
        'max': float(vals.max()),
        'median': float(vals.median()),
        'q25': float(vals.quantile(0.25)),
        'q75': float(vals.quantile(0.75)),
        'skewness': float(vals.skew()),
        'kurtosis': float(vals.kurtosis()),
    }
    print(f"  {col:20s}: mean={vals.mean():.3f}  std={vals.std():.3f}  "
          f"range=[{vals.min():.3f}, {vals.max():.3f}]  skew={vals.skew():.2f}")

# -- STEP 4: DYNAMIC GENRE PROFILES ------------------------
print("\n" + "=" * 70)
print("STEP 4: Building genre audio profiles")
print("=" * 70)

genre_profiles = {}
genre_means = df.groupby(genre_col)[feature_cols].mean()
genre_stds = df.groupby(genre_col)[feature_cols].std()
genre_counts = df[genre_col].value_counts()

for genre in genres:
    means = genre_means.loc[genre].to_dict()
    stds = genre_stds.loc[genre].to_dict()
    genre_profiles[genre] = {
        'means': {k: round(float(v), 4) for k, v in means.items()},
        'stds': {k: round(float(v), 4) for k, v in stds.items()},
        'track_count': int(genre_counts.get(genre, 0)),
    }
    e = means.get('energy', 0)
    v = means.get('valence', 0)
    d = means.get('danceability', 0)
    a = means.get('acousticness', 0)
    print(f"  {genre:25s} ({genre_counts.get(genre,0):>5,} tracks): "
          f"E={e:.2f}  V={v:.2f}  D={d:.2f}  A={a:.2f}")

# -- STEP 5: GENRE CLUSTERING (ENHANCED METRICS) -----------
print("\n" + "=" * 70)
print("STEP 5: Clustering similar genres (multi-metric evaluation)")
print("=" * 70)

genre_matrix = genre_means.values
scaler = StandardScaler()
genre_scaled = scaler.fit_transform(genre_matrix)

best_k = 5
best_sil_genre = -1
genre_cluster_scores = []

for k in range(5, min(16, len(genres))):
    km = KMeans(n_clusters=k, random_state=SEED, n_init=10)
    labels = km.fit_predict(genre_scaled)
    if len(set(labels)) > 1:
        sil = silhouette_score(genre_scaled, labels)
        ch = calinski_harabasz_score(genre_scaled, labels)
        db = davies_bouldin_score(genre_scaled, labels)
        genre_cluster_scores.append({'k': k, 'silhouette': round(sil, 4),
                                      'calinski_harabasz': round(ch, 2),
                                      'davies_bouldin': round(db, 4)})
        if sil > best_sil_genre:
            best_sil_genre = sil
            best_k = k
        print(f"  K={k:2d}: silhouette={sil:.4f}  CH={ch:.1f}  DB={db:.4f}")

print(f"Selected K={best_k} (silhouette={best_sil_genre:.4f})")

kmeans_genre = KMeans(n_clusters=best_k, random_state=SEED, n_init=10)
genre_cluster_labels = kmeans_genre.fit_predict(genre_scaled)

genre_clusters = {}
for i, genre in enumerate(genres):
    cluster_id = int(genre_cluster_labels[i])
    if cluster_id not in genre_clusters:
        genre_clusters[cluster_id] = []
    genre_clusters[cluster_id].append(genre)

print(f"\nGenre clusters ({best_k}):")
for cid, glist in sorted(genre_clusters.items()):
    cluster_energy = np.mean([genre_profiles[g]['means'].get('energy', 0) for g in glist])
    cluster_valence = np.mean([genre_profiles[g]['means'].get('valence', 0) for g in glist])
    print(f"  Cluster {cid} (E={cluster_energy:.2f}, V={cluster_valence:.2f}): {', '.join(glist)}")

# -- STEP 6: DEEP AUTOENCODER / VAE TRAINING ---------------
print("\n" + "=" * 70)
arch_name = "Variational Autoencoder (VAE)" if USE_VAE else "Deep Autoencoder (Residual)"
print(f"STEP 6: Training {arch_name}")
print("=" * 70)

INPUT_DIM = len(mood_features)
print(f"Architecture: {INPUT_DIM} -> 64 -> Res(64) -> 32 -> Res(32) -> {LATENT_DIM} "
      f"-> 32 -> Res(32) -> 64 -> Res(64) -> {INPUT_DIM}")
print(f"Config: epochs={EPOCHS}, batch={BATCH_SIZE}, lr={LEARNING_RATE}, val_split={VAL_SPLIT}")
print(f"Device: {device}")

mood_matrix = df[mood_features].fillna(0).values.astype(np.float32)
mood_scaler = StandardScaler()
mood_scaled = mood_scaler.fit_transform(mood_matrix)

global_medians = {f: float(np.median(mood_matrix[:, i])) for i, f in enumerate(mood_features)}

X_train, X_val = train_test_split(mood_scaled, test_size=VAL_SPLIT, random_state=SEED)
print(f"Train: {len(X_train):,} samples | Val: {len(X_val):,} samples")

train_tensor = torch.tensor(X_train, dtype=torch.float32)
val_tensor = torch.tensor(X_val, dtype=torch.float32)
train_loader = DataLoader(TensorDataset(train_tensor), batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(TensorDataset(val_tensor), batch_size=BATCH_SIZE, shuffle=False)

if USE_VAE:
    model = SongVAE(INPUT_DIM, LATENT_DIM).to(device)
else:
    model = SongAutoencoder(INPUT_DIM, LATENT_DIM).to(device)

total_params = sum(p.numel() for p in model.parameters())
trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"Model parameters: {total_params:,} total, {trainable_params:,} trainable")

optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(optimizer, T_0=20, T_mult=2, eta_min=1e-5)
criterion = nn.MSELoss()

train_losses = []
val_losses = []
best_val_loss = float('inf')
best_state = None
patience_counter = 0
PATIENCE = 15

for epoch in range(1, EPOCHS + 1):
    model.train()
    epoch_train_loss = 0.0
    n_train = 0
    for (batch_x,) in train_loader:
        batch_x = batch_x.to(device)

        if USE_VAE:
            recon, mu, logvar, z = model(batch_x)
            recon_loss = criterion(recon, batch_x)
            kl_loss = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
            loss = recon_loss + 0.1 * kl_loss
        else:
            recon, z = model(batch_x)
            loss = criterion(recon, batch_x)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        epoch_train_loss += loss.item() * batch_x.size(0)
        n_train += batch_x.size(0)

    scheduler.step()
    avg_train = epoch_train_loss / n_train

    model.eval()
    epoch_val_loss = 0.0
    n_val = 0
    with torch.no_grad():
        for (batch_x,) in val_loader:
            batch_x = batch_x.to(device)
            if USE_VAE:
                recon, mu, logvar, z = model(batch_x)
                recon_loss = criterion(recon, batch_x)
                kl_loss = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
                loss = recon_loss + 0.1 * kl_loss
            else:
                recon, z = model(batch_x)
                loss = criterion(recon, batch_x)
            epoch_val_loss += loss.item() * batch_x.size(0)
            n_val += batch_x.size(0)

    avg_val = epoch_val_loss / n_val
    train_losses.append(avg_train)
    val_losses.append(avg_val)

    if avg_val < best_val_loss:
        best_val_loss = avg_val
        best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        patience_counter = 0
    else:
        patience_counter += 1

    if epoch % 10 == 0 or epoch == 1 or epoch == EPOCHS:
        lr_now = optimizer.param_groups[0]['lr']
        print(f"  Epoch {epoch:3d}/{EPOCHS}  train_loss={avg_train:.6f}  "
              f"val_loss={avg_val:.6f}  lr={lr_now:.2e}  patience={patience_counter}/{PATIENCE}")

    if patience_counter >= PATIENCE:
        print(f"  Early stopping at epoch {epoch} (no improvement for {PATIENCE} epochs)")
        break

if best_state is not None:
    model.load_state_dict(best_state)
    print(f"Restored best model (val_loss={best_val_loss:.6f})")

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(train_losses, label='Train Loss', linewidth=1.5)
ax.plot(val_losses, label='Val Loss', linewidth=1.5)
ax.set_xlabel('Epoch')
ax.set_ylabel('Loss')
ax.set_title(f'{arch_name} Training Curve')
ax.legend()
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig('training_curve.png', dpi=150)
plt.close(fig)
print("Saved: training_curve.png")

print(f"\nComputing reconstruction quality (per-feature R-squared)...")
model.eval()
with torch.no_grad():
    X_all_tensor = torch.tensor(mood_scaled, dtype=torch.float32).to(device)
    if USE_VAE:
        recon_all = model(X_all_tensor)[0].cpu().numpy()
        latent_all = model.encode(X_all_tensor).cpu().numpy()
    else:
        recon_all, _ = model(X_all_tensor)
        recon_all = recon_all.cpu().numpy()
        latent_all = model.encode(X_all_tensor).cpu().numpy()

r_squared = compute_r_squared(mood_scaled, recon_all)
reconstruction_quality = {}
for i, f in enumerate(mood_features):
    reconstruction_quality[f] = round(float(r_squared[i]), 4)
    print(f"  {f:30s}: R2 = {r_squared[i]:.4f}")

mean_r2 = float(np.mean(r_squared))
print(f"  {'MEAN R-SQUARED':30s}: {mean_r2:.4f}")
print(f"Latent shape: {latent_all.shape}")

# -- STEP 7: GMM SOFT CLUSTERING ON LATENT SPACE -----------
print("\n" + "=" * 70)
print("STEP 7: GMM soft clustering on latent space (BIC + silhouette + CH + DB)")
print("=" * 70)

sample_size = min(UMAP_SAMPLE_SIZE, len(df))
sample_indices = np.random.RandomState(SEED).choice(len(df), sample_size, replace=False)
latent_sample = latent_all[sample_indices]

cluster_eval_results = []
best_k_mood = 8
best_sil_mood = -1

k_lo, k_hi = CLUSTER_K_RANGE
print(f"Evaluating K in [{k_lo}, {k_hi}] on {sample_size:,} samples...\n")

for k in range(k_lo, k_hi + 1):
    gmm = GaussianMixture(n_components=k, random_state=SEED, n_init=3,
                           covariance_type='full', max_iter=200)
    gmm.fit(latent_sample)
    bic_val = gmm.bic(latent_sample)

    km = KMeans(n_clusters=k, random_state=SEED, n_init=5, max_iter=200)
    km_labels = km.fit_predict(latent_sample)

    if len(set(km_labels)) > 1:
        sil = silhouette_score(latent_sample, km_labels, sample_size=min(10000, sample_size))
        ch = calinski_harabasz_score(latent_sample, km_labels)
        db = davies_bouldin_score(latent_sample, km_labels)

        entry = {
            'k': k, 'silhouette': round(sil, 4), 'calinski_harabasz': round(ch, 2),
            'davies_bouldin': round(db, 4), 'bic': round(bic_val, 2),
        }
        cluster_eval_results.append(entry)

        if sil > best_sil_mood:
            best_sil_mood = sil
            best_k_mood = k

        print(f"  K={k:2d}: sil={sil:.4f}  CH={ch:.1f}  DB={db:.4f}  BIC={bic_val:.0f}")

print(f"\nSelected K={best_k_mood} (best silhouette={best_sil_mood:.4f})")

print(f"\nFitting final GMM (K={best_k_mood}) on all {len(df):,} tracks...")
gmm_final = GaussianMixture(n_components=best_k_mood, random_state=SEED, n_init=5,
                             covariance_type='full', max_iter=300)
gmm_final.fit(latent_all)
soft_probs = gmm_final.predict_proba(latent_all)

print(f"Fitting final KMeans (K={best_k_mood}) for centroid-based labeling...")
kmeans_mood = KMeans(n_clusters=best_k_mood, random_state=SEED, n_init=10)
kmeans_mood.fit(latent_all)
df['mood_cluster'] = kmeans_mood.predict(latent_all)

# -- STEP 8: RUSSELL'S CIRCUMPLEX AUTO-LABELING ------------
print("\n" + "=" * 70)
print("STEP 8: Russell's Circumplex mood auto-labeling")
print("=" * 70)

cluster_labels = {}
cluster_profiles = {}
used_labels = set()

for cid in range(best_k_mood):
    mask = df['mood_cluster'] == cid
    cluster_count = int(mask.sum())

    latent_centroid = kmeans_mood.cluster_centers_[cid]
    latent_centroid_tensor = torch.tensor(latent_centroid, dtype=torch.float32).unsqueeze(0).to(device)
    model.eval()
    with torch.no_grad():
        reconstructed = model.decoder(latent_centroid_tensor).cpu().numpy()[0]
    centroid_original = mood_scaler.inverse_transform(reconstructed.reshape(1, -1))[0]

    label = circumplex_label(centroid_original, mood_features, global_medians, used_labels)
    used_labels.add(label)

    cluster_labels[cid] = label

    profile = {f: round(float(centroid_original[i]), 4) for i, f in enumerate(mood_features)}
    profile['track_count'] = cluster_count
    profile['percentage'] = round(cluster_count / len(df) * 100, 1)

    soft_mean = soft_probs[mask.values].mean(axis=0).tolist()
    profile['gmm_soft_distribution'] = {
        cluster_labels.get(j, f'cluster_{j}'): round(soft_mean[j], 4)
        for j in range(len(soft_mean))
        if j in cluster_labels
    }

    cluster_profiles[label] = profile

    pct = cluster_count / len(df) * 100
    v_val = centroid_original[mood_features.index('valence')] if 'valence' in mood_features else 0
    e_val = centroid_original[mood_features.index('energy')] if 'energy' in mood_features else 0
    print(f"  Cluster {cid} -> \"{label}\" ({cluster_count:,} tracks, {pct:.1f}%)"
          f"  V={v_val:.3f} E={e_val:.3f}")

df['mood'] = df['mood_cluster'].map(cluster_labels)

mood_dist = df['mood'].value_counts()
print(f"\nFinal mood distribution ({len(mood_dist)} categories):")
for mood, count in mood_dist.items():
    print(f"  {mood}: {count:,} ({count/len(df)*100:.1f}%)")

encoder_path = 'song_encoder.pt'
save_dict = {
    'model_type': 'vae' if USE_VAE else 'autoencoder',
    'model_state_dict': model.state_dict(),
    'input_dim': INPUT_DIM,
    'latent_dim': LATENT_DIM,
    'mood_features': mood_features,
    'scaler_mean': mood_scaler.mean_.tolist(),
    'scaler_scale': mood_scaler.scale_.tolist(),
    'global_medians': global_medians,
    'cluster_centers_latent': kmeans_mood.cluster_centers_.tolist(),
    'cluster_labels': cluster_labels,
    'reconstruction_r_squared': reconstruction_quality,
    'mean_r_squared': mean_r2,
    'best_val_loss': best_val_loss,
    'gmm_means': gmm_final.means_.tolist(),
    'gmm_covariances': gmm_final.covariances_.tolist(),
    'gmm_weights': gmm_final.weights_.tolist(),
}
torch.save(save_dict, encoder_path)
print(f"\nSaved encoder model: {encoder_path}")

# -- STEP 9: UMAP LATENT SPACE VISUALIZATION ---------------
print("\n" + "=" * 70)
print("STEP 9: UMAP latent space visualization")
print("=" * 70)

umap_sample = min(UMAP_SAMPLE_SIZE, len(df))
viz_indices = np.random.RandomState(SEED).choice(len(df), umap_sample, replace=False)
latent_viz = latent_all[viz_indices]
mood_viz = df['mood'].iloc[viz_indices].values
genre_viz = df[genre_col].iloc[viz_indices].values if genre_col else None

try:
    from umap import UMAP
    reducer = UMAP(n_components=2, n_neighbors=30, min_dist=0.3, random_state=SEED, metric='cosine')
    embed_2d = reducer.fit_transform(latent_viz)
    projection_method = 'UMAP'
    print(f"UMAP projection complete ({umap_sample:,} points)")
except ImportError:
    from sklearn.manifold import TSNE
    reducer = TSNE(n_components=2, random_state=SEED, perplexity=30, n_iter=1000)
    embed_2d = reducer.fit_transform(latent_viz)
    projection_method = 't-SNE'
    print(f"UMAP not available, falling back to t-SNE ({umap_sample:,} points)")

unique_moods = sorted(set(mood_viz))
mood_cmap = cm.get_cmap('tab20', len(unique_moods))
mood_color_map = {m: mood_cmap(i) for i, m in enumerate(unique_moods)}

fig, ax = plt.subplots(figsize=(14, 10))
for mood_label in unique_moods:
    mask_v = mood_viz == mood_label
    ax.scatter(embed_2d[mask_v, 0], embed_2d[mask_v, 1], c=[mood_color_map[mood_label]],
               label=mood_label, s=3, alpha=0.5)
ax.set_title(f'Latent Space ({projection_method}) - Colored by Mood', fontsize=14)
ax.set_xlabel(f'{projection_method}-1')
ax.set_ylabel(f'{projection_method}-2')
ax.legend(markerscale=5, fontsize=8, loc='best', framealpha=0.8)
ax.grid(True, alpha=0.2)
fig.tight_layout()
fig.savefig('latent_mood_viz.png', dpi=150)
plt.close(fig)
print("Saved: latent_mood_viz.png")

if genre_viz is not None:
    top_genres = [g for g, _ in Counter(genre_viz).most_common(20)]
    genre_cmap = cm.get_cmap('tab20', len(top_genres))

    fig, ax = plt.subplots(figsize=(14, 10))
    for i, g in enumerate(top_genres):
        mask_g = genre_viz == g
        ax.scatter(embed_2d[mask_g, 0], embed_2d[mask_g, 1], c=[genre_cmap(i)],
                   label=g, s=3, alpha=0.5)
    other_mask = ~np.isin(genre_viz, top_genres)
    if other_mask.any():
        ax.scatter(embed_2d[other_mask, 0], embed_2d[other_mask, 1], c='lightgray',
                   label='other', s=1, alpha=0.2)
    ax.set_title(f'Latent Space ({projection_method}) - Colored by Genre (Top 20)', fontsize=14)
    ax.set_xlabel(f'{projection_method}-1')
    ax.set_ylabel(f'{projection_method}-2')
    ax.legend(markerscale=5, fontsize=7, loc='best', framealpha=0.8, ncol=2)
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig('latent_genre_viz.png', dpi=150)
    plt.close(fig)
    print("Saved: latent_genre_viz.png")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].bar(range(len(mood_dist)), mood_dist.values, color='steelblue')
axes[0].set_xticks(range(len(mood_dist)))
axes[0].set_xticklabels(mood_dist.index, rotation=45, ha='right', fontsize=8)
axes[0].set_title('Mood Distribution')
axes[0].set_ylabel('Track Count')

r2_vals = list(reconstruction_quality.values())
r2_names = list(reconstruction_quality.keys())
colors = ['green' if v > 0.8 else 'orange' if v > 0.5 else 'red' for v in r2_vals]
axes[1].barh(range(len(r2_vals)), r2_vals, color=colors)
axes[1].set_yticks(range(len(r2_names)))
axes[1].set_yticklabels(r2_names, fontsize=7)
axes[1].set_xlim(0, 1.05)
axes[1].set_title('Per-Feature Reconstruction R-squared')
axes[1].axvline(x=0.8, color='gray', linestyle='--', alpha=0.5)
fig.tight_layout()
fig.savefig('diagnostics.png', dpi=150)
plt.close(fig)
print("Saved: diagnostics.png")

# -- STEP 10: MOOD x GENRE MATRIX --------------------------
print("\n" + "=" * 70)
print("STEP 10: Building mood x genre probability matrix")
print("=" * 70)

mood_genre_matrix = pd.crosstab(df[genre_col], df['mood'], normalize='index').round(3)
print(mood_genre_matrix.to_string())

# -- STEP 11: KEY & MODE ANALYSIS --------------------------
print("\n" + "=" * 70)
print("STEP 11: Musical key and mode analysis")
print("=" * 70)

key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
key_analysis = {}
total = len(df)

if 'key' in df.columns:
    key_dist = df['key'].value_counts().sort_index()
    for k_idx, count in key_dist.items():
        key_name = key_names[int(k_idx)] if int(k_idx) < len(key_names) else f"Key_{k_idx}"
        key_analysis[key_name] = {
            'count': int(count),
            'percentage': round(count / total * 100, 1)
        }
        print(f"  {key_name}: {count:,} tracks ({count/total*100:.1f}%)")

    key_mood = pd.crosstab(
        df['key'].map(lambda x: key_names[int(x)] if int(x) < len(key_names) else f"Key_{x}"),
        df['mood'], normalize='index'
    ).round(3)
    key_analysis['mood_distribution'] = key_mood.to_dict()

mode_analysis = {}
if 'mode' in df.columns:
    mode_dist_raw = df['mode'].value_counts()
    mode_analysis = {
        'major': {'count': int(mode_dist_raw.get(1, 0)),
                  'percentage': round(mode_dist_raw.get(1, 0) / total * 100, 1)},
        'minor': {'count': int(mode_dist_raw.get(0, 0)),
                  'percentage': round(mode_dist_raw.get(0, 0) / total * 100, 1)},
    }
    print(f"\n  Major: {mode_analysis['major']['count']:,} ({mode_analysis['major']['percentage']}%)")
    print(f"  Minor: {mode_analysis['minor']['count']:,} ({mode_analysis['minor']['percentage']}%)")

# -- STEP 12: TEMPO ZONES ----------------------------------
print("\n" + "=" * 70)
print("STEP 12: Tempo zone analysis")
print("=" * 70)

tempo_analysis = {}
if 'tempo' in df.columns:
    tempo_vals = df['tempo'].dropna()
    tempo_bins = [
        ('very_slow', 0, 60),
        ('slow', 60, 90),
        ('moderate', 90, 120),
        ('fast', 120, 150),
        ('very_fast', 150, 300),
    ]
    for zone, lo, hi in tempo_bins:
        count = int(((tempo_vals >= lo) & (tempo_vals < hi)).sum())
        tempo_analysis[zone] = {
            'range': [lo, hi],
            'count': count,
            'percentage': round(count / len(tempo_vals) * 100, 1)
        }
        print(f"  {zone:12s} ({lo:3d}-{hi:3d} BPM): {count:,} tracks ({count/len(tempo_vals)*100:.1f}%)")

    tempo_mood = pd.DataFrame({
        'tempo_zone': pd.cut(df['tempo'], bins=[0, 60, 90, 120, 150, 300],
                             labels=['very_slow', 'slow', 'moderate', 'fast', 'very_fast']),
        'mood': df['mood']
    })
    tempo_mood_matrix = pd.crosstab(tempo_mood['tempo_zone'], tempo_mood['mood'], normalize='index').round(3)
    tempo_analysis['mood_distribution'] = tempo_mood_matrix.to_dict()

# -- STEP 13: GENRE SIMILARITY MATRIX ----------------------
print("\n" + "=" * 70)
print("STEP 13: Computing genre cosine similarity")
print("=" * 70)

genre_sim = cosine_similarity(genre_scaled)
genre_similarity = {}
for i, g1 in enumerate(genres):
    sim_scores = list(enumerate(genre_sim[i]))
    sim_scores.sort(key=lambda x: x[1], reverse=True)
    top_similar = [(genres[idx], round(float(score), 3)) for idx, score in sim_scores[1:8]]
    genre_similarity[g1] = top_similar
    top3_str = ', '.join([f'{g}({s})' for g, s in top_similar[:3]])
    print(f"  {g1:25s} -> {top3_str}")

# -- STEP 14: ARTIST-LEVEL MOOD FINGERPRINTS ----------------
print("\n" + "=" * 70)
print("STEP 14: Artist-level mood fingerprints")
print("=" * 70)

artist_col = 'artists' if 'artists' in df.columns else 'artist_name' if 'artist_name' in df.columns else None
artist_profiles = {}
top_artists_per_mood = {}

if artist_col:
    artist_counts = df[artist_col].value_counts()
    qualified_artists = artist_counts[artist_counts >= MIN_ARTIST_TRACKS].index.tolist()
    print(f"Artists with >= {MIN_ARTIST_TRACKS} tracks: {len(qualified_artists):,} / {df[artist_col].nunique():,}")

    df_qualified = df[df[artist_col].isin(qualified_artists)]

    artist_mood_dist = pd.crosstab(df_qualified[artist_col], df_qualified['mood'], normalize='index').round(3)
    artist_feature_means = df_qualified.groupby(artist_col)[base_mood_features].mean()

    for artist in qualified_artists[:500]:
        mood_row = artist_mood_dist.loc[artist].to_dict() if artist in artist_mood_dist.index else {}
        feat_row = artist_feature_means.loc[artist].to_dict() if artist in artist_feature_means.index else {}
        dominant_mood = max(mood_row, key=mood_row.get) if mood_row else 'unknown'
        artist_profiles[artist] = {
            'track_count': int(artist_counts[artist]),
            'dominant_mood': dominant_mood,
            'mood_distribution': {k: round(float(v), 3) for k, v in mood_row.items()},
            'audio_fingerprint': {k: round(float(v), 4) for k, v in feat_row.items()},
        }

    for mood_label in mood_dist.index:
        mood_artists = df_qualified[df_qualified['mood'] == mood_label][artist_col].value_counts().head(10)
        top_artists_per_mood[mood_label] = [
            {'artist': a, 'track_count': int(c)} for a, c in mood_artists.items()
        ]
        top3 = ', '.join([f"{a}({c})" for a, c in mood_artists.head(3).items()])
        print(f"  {mood_label:30s}: {top3}")

    print(f"\nBuilt profiles for {len(artist_profiles):,} artists")
else:
    print("No artist column found, skipping artist analysis")

# -- STEP 15: MOOD TRANSITION PROBABILITY MATRIX ------------
print("\n" + "=" * 70)
print("STEP 15: Mood transition probability matrix")
print("=" * 70)

album_col = 'album_name' if 'album_name' in df.columns else None
transition_matrix = {}

if album_col and 'track_number' in df.columns:
    df_sorted = df.sort_values([album_col, 'track_number'])
    albums_with_multiple = df_sorted.groupby(album_col).filter(lambda x: len(x) >= 3)

    transitions = []
    for album, group in albums_with_multiple.groupby(album_col):
        moods_seq = group['mood'].tolist()
        for i in range(len(moods_seq) - 1):
            transitions.append((moods_seq[i], moods_seq[i + 1]))

    if transitions:
        trans_df = pd.DataFrame(transitions, columns=['from_mood', 'to_mood'])
        trans_matrix = pd.crosstab(trans_df['from_mood'], trans_df['to_mood'], normalize='index').round(3)
        transition_matrix = trans_matrix.to_dict()
        print(f"Computed from {len(transitions):,} sequential transitions across albums")
        print(trans_matrix.to_string())
    else:
        print("No sequential transitions found")
else:
    print("No album/track_number columns, computing artist-level co-occurrence transitions")
    mood_pairs = []
    if artist_col:
        for artist, group in df.groupby(artist_col):
            if len(group) >= 3:
                moods_seq = group['mood'].tolist()
                for i in range(len(moods_seq) - 1):
                    mood_pairs.append((moods_seq[i], moods_seq[i + 1]))

        if mood_pairs:
            trans_df = pd.DataFrame(mood_pairs, columns=['from_mood', 'to_mood'])
            trans_matrix = pd.crosstab(trans_df['from_mood'], trans_df['to_mood'], normalize='index').round(3)
            transition_matrix = trans_matrix.to_dict()
            print(f"Computed from {len(mood_pairs):,} artist-level transitions")
            print(trans_matrix.to_string())

# -- STEP 16: BUILD KNOWLEDGE BASE JSON --------------------
print("\n" + "=" * 70)
print("STEP 16: Building enriched knowledge base JSON")
print("=" * 70)

knowledge_base = {
    'metadata': {
        'total_tracks': len(df),
        'total_genres': len(genres),
        'total_artists': int(df[artist_col].nunique()) if artist_col else 0,
        'features': feature_cols,
        'mood_features': mood_features,
        'feature_stats': feature_stats,
        'builder_config': {
            'model_type': 'vae' if USE_VAE else 'autoencoder',
            'latent_dim': LATENT_DIM,
            'epochs_trained': len(train_losses),
            'best_val_loss': round(best_val_loss, 6),
            'mean_reconstruction_r2': round(mean_r2, 4),
        },
    },
    'genres': {
        'list': genres,
        'profiles': genre_profiles,
        'clusters': {str(k): v for k, v in genre_clusters.items()},
        'cluster_eval_scores': genre_cluster_scores,
        'similarity': genre_similarity,
    },
    'moods': {
        'classifier': f"{'vae' if USE_VAE else 'autoencoder'}_gmm_kmeans",
        'labeling_method': 'russells_circumplex',
        'latent_dim': LATENT_DIM,
        'architecture': (f'{INPUT_DIM} -> 64 -> Res(64) -> 32 -> Res(32) -> {LATENT_DIM} '
                         f'-> 32 -> Res(32) -> 64 -> Res(64) -> {INPUT_DIM}'),
        'optimal_k': best_k_mood,
        'cluster_eval_results': cluster_eval_results,
        'features_used': mood_features,
        'global_medians': global_medians,
        'reconstruction_quality': reconstruction_quality,
        'cluster_profiles': cluster_profiles,
        'distribution': {mood: {'count': int(count), 'percentage': round(count/len(df)*100, 1)}
                        for mood, count in mood_dist.items()},
    },
    'mood_genre_matrix': {
        genre: {mood: float(val) for mood, val in row.items()}
        for genre, row in mood_genre_matrix.to_dict(orient='index').items()
    },
    'musical': {
        'key_analysis': {k: v for k, v in key_analysis.items() if k != 'mood_distribution'},
        'mode_analysis': mode_analysis,
        'tempo_analysis': {k: v for k, v in tempo_analysis.items() if k != 'mood_distribution'},
    },
    'artists': {
        'min_track_threshold': MIN_ARTIST_TRACKS,
        'qualified_count': len(artist_profiles),
        'top_per_mood': top_artists_per_mood,
    },
    'transitions': {
        'method': 'album_sequential' if album_col else 'artist_cooccurrence',
        'matrix': transition_matrix,
    },
    'song_profile_template': {
        'description': 'Template for embedding song metadata into text for RAG',
        'fields': ['title', 'artist', 'genre', 'mood', 'mood_confidence', 'tempo_zone',
                   'energy_level', 'valence_level', 'key', 'mode', 'danceability_level',
                   'acousticness_level', 'groove_factor'],
        'example': ('Title: X, Artist: Y, Genre: rock, Mood: euphoric_groovy (0.82), '
                    'Tempo: fast (140 BPM), Energy: high (0.85), Valence: medium (0.55), '
                    'Key: A, Mode: minor, Dance: medium, Acoustic: low, Groove: 0.42'),
    },
}

kb_path = 'music_knowledge_base.json'
with open(kb_path, 'w') as f:
    json.dump(knowledge_base, f, indent=2, default=str)
print(f"Saved: {kb_path} ({os.path.getsize(kb_path) / 1024:.0f} KB)")

genre_profiles_df = pd.DataFrame({g: p['means'] for g, p in genre_profiles.items()}).T
genre_profiles_df.to_csv('genre_profiles_full.csv')
print("Saved: genre_profiles_full.csv")

mood_df = pd.DataFrame([
    {'mood': mood, 'count': count, 'percentage': round(count/len(df)*100, 1)}
    for mood, count in mood_dist.items()
])
mood_df.to_csv('mood_distribution.csv', index=False)
print("Saved: mood_distribution.csv")

mood_genre_matrix.to_csv('mood_genre_matrix.csv')
print("Saved: mood_genre_matrix.csv")

if artist_profiles:
    artist_df = pd.DataFrame([
        {'artist': a, 'dominant_mood': p['dominant_mood'], 'track_count': p['track_count'],
         **{f'mood_{k}': v for k, v in p['mood_distribution'].items()},
         **{f'feat_{k}': v for k, v in p['audio_fingerprint'].items()}}
        for a, p in artist_profiles.items()
    ])
    artist_df.to_csv('artist_profiles.csv', index=False)
    print(f"Saved: artist_profiles.csv ({len(artist_profiles):,} artists)")

if transition_matrix:
    trans_df_out = pd.DataFrame(transition_matrix)
    trans_df_out.to_csv('mood_transitions.csv')
    print("Saved: mood_transitions.csv")

soft_probs_df = pd.DataFrame(soft_probs, columns=[cluster_labels.get(i, f'cluster_{i}')
                                                    for i in range(best_k_mood)])
soft_probs_df.to_csv('mood_soft_probabilities.csv', index=False)
print(f"Saved: mood_soft_probabilities.csv ({len(soft_probs_df):,} rows)")

# -- STEP 17: SUMMARY --------------------------------------
print("\n" + "=" * 70)
print("KNOWLEDGE BASE BUILD COMPLETE")
print("=" * 70)
print(f"Total tracks analyzed:     {len(df):,}")
print(f"Audio features:            {len(feature_cols)} raw + "
      f"{len(mood_features) - len(base_mood_features)} engineered = {len(mood_features)} total")
print(f"Genres:                    {len(genres)} ({best_k} clusters)")
print(f"Mood categories:           {len(mood_dist)} (K={best_k_mood}, {arch_name})")
print(f"Latent dimension:          {LATENT_DIM}")
print(f"Reconstruction quality:    mean R2 = {mean_r2:.4f}")
print(f"Best validation loss:      {best_val_loss:.6f}")
print(f"Artist profiles:           {len(artist_profiles):,}")
print(f"Mood transitions:          {'computed' if transition_matrix else 'not available'}")
print(f"\nOutput files:")
print(f"  1. {kb_path:40s} - Enriched knowledge base (JSON)")
print(f"  2. {'genre_profiles_full.csv':40s} - Genre audio profiles")
print(f"  3. {'mood_distribution.csv':40s} - Mood label distribution")
print(f"  4. {'mood_genre_matrix.csv':40s} - Mood x genre probability matrix")
print(f"  5. {encoder_path:40s} - Trained encoder + GMM + KMeans state")
print(f"  6. {'training_curve.png':40s} - Train/val loss curve plot")
print(f"  7. {'latent_mood_viz.png':40s} - UMAP latent space (mood colored)")
print(f"  8. {'latent_genre_viz.png':40s} - UMAP latent space (genre colored)")
print(f"  9. {'diagnostics.png':40s} - Mood distribution + R2 bar charts")
print(f" 10. {'artist_profiles.csv':40s} - Artist mood fingerprints")
print(f" 11. {'mood_transitions.csv':40s} - Mood transition probabilities")
print(f" 12. {'mood_soft_probabilities.csv':40s} - GMM soft cluster probabilities")

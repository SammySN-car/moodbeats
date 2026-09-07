<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import client from '../../../api/client'

const router = useRouter()
const name = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleSignup() {
  error.value = ''
  loading.value = true
  try {
    await client.post('/auth/register', {
      name: name.value,
      email: email.value,
      password: password.value
    })
    router.push('/login')
  } catch (err) {
    error.value = err.response?.data?.detail || 'Registration failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-container">
    <div class="auth-card animate-in">
      <div class="auth-brand">
        <div class="auth-logo">
          <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
            <defs>
              <linearGradient id="signupGrad" x1="0" y1="0" x2="52" y2="52">
                <stop offset="0%" stop-color="#f59e0b"/>
                <stop offset="100%" stop-color="#f97316"/>
              </linearGradient>
            </defs>
            <rect width="52" height="52" rx="16" fill="url(#signupGrad)"/>
            <path d="M16 36V20L36 13V29" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="16" cy="36" r="4.5" fill="#fff" opacity="0.9"/>
            <circle cx="36" cy="29" r="4.5" fill="#fff" opacity="0.9"/>
          </svg>
        </div>
        <h1 class="auth-title">Create Account</h1>
        <p class="auth-sub">Join AI music discovery</p>
      </div>

      <form @submit.prevent="handleSignup" class="auth-form">
        <div class="field">
          <label class="field-label">Name</label>
          <input v-model="name" type="text" placeholder="Your name" class="input-text" required />
        </div>
        <div class="field">
          <label class="field-label">Email</label>
          <input v-model="email" type="email" placeholder="you@example.com" class="input-text" required />
        </div>
        <div class="field">
          <label class="field-label">Password</label>
          <input v-model="password" type="password" placeholder="Min 6 characters" class="input-text" required minlength="6" />
        </div>

        <div v-if="error" class="alert-error">{{ error }}</div>

        <button type="submit" class="btn btn-primary w-full submit-btn" :disabled="loading">
          <span v-if="loading">Creating account...</span>
          <span v-else>Create Account</span>
        </button>
      </form>

      <div class="auth-sep"><span>or</span></div>

      <p class="auth-switch">
        Already have an account?
        <router-link to="/login">Sign in</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-card {
  width: 100%;
  max-width: 400px;
  background: rgba(18, 18, 32, 0.7);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: 2.5rem;
  box-shadow: var(--shadow-lg), 0 0 100px rgba(245, 158, 11, 0.04);
}

.auth-brand { text-align: center; margin-bottom: 2rem; }
.auth-logo { margin-bottom: 1.25rem; }

.auth-title {
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.auth-sub {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: 0.3rem;
}

.auth-form { display: flex; flex-direction: column; gap: 1rem; }

.field { display: flex; flex-direction: column; gap: 0.35rem; }

.field-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.submit-btn {
  margin-top: 0.5rem;
  padding: 0.75rem;
  font-size: 0.88rem;
}

.auth-sep {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin: 1.5rem 0;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.auth-sep::before, .auth-sep::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

.auth-switch {
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.auth-switch a {
  color: var(--amber);
  font-weight: 700;
  margin-left: 0.3rem;
}
</style>

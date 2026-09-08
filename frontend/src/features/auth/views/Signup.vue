<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import client from '../../../api/client'

const router = useRouter()
const name = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function handleSignup() {
  error.value = ''
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }
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
  <main class="auth-page">
    <section class="auth-card">
      <router-link to="/" class="brand"><span class="mark"><i></i><i></i><i></i></span>Mood<span>Beats</span></router-link>
      <div class="intro">
        <p class="eyebrow">JOIN MOODBEATS</p>
        <h1>Make music feel personal.</h1>
        <p>Create a profile that learns what moves you.</p>
      </div>
      <form @submit.prevent="handleSignup">
        <label class="field">
          <span>Name</span>
          <input v-model.trim="name" autocomplete="name" placeholder="Your name" required />
        </label>
        <label class="field">
          <span>Email</span>
          <input v-model.trim="email" type="email" autocomplete="email" placeholder="you@example.com" required />
        </label>
        <label class="field">
          <span>Password</span>
          <input v-model="password" type="password" autocomplete="new-password" placeholder="Create a password" required minlength="6" />
        </label>
        <label class="field">
          <span>Confirm password</span>
          <input v-model="confirmPassword" type="password" autocomplete="new-password" placeholder="Repeat your password" required />
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" type="submit" :disabled="loading">{{ loading ? 'Creating account...' : 'Create account' }}</button>
      </form>
      <p class="switch">Already have an account? <router-link to="/login">Log in</router-link></p>
    </section>
  </main>
</template>

<style scoped>
.auth-page{min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 50% 0,rgba(245,185,66,.13),transparent 42%),#0b0d10}
.auth-card{width:min(100%,430px);padding:32px;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(13,16,20,.76)}
.brand{display:flex;align-items:center;gap:9px;color:#f4f5f7;font-size:20px;font-weight:750;letter-spacing:-.04em;text-decoration:none}
.brand>span:last-child{color:#f5b942}
.mark{display:flex;align-items:end;gap:2px;height:22px}
.mark i{width:4px;border-radius:4px;background:#f5b942}
.mark i:nth-child(1){height:11px}
.mark i:nth-child(2){height:19px}
.mark i:nth-child(3){height:14px}
.intro{margin:38px 0 22px}
.eyebrow{margin:0 0 10px;color:#f5b942;font-size:10px;font-weight:800;letter-spacing:.15em}
.intro h1{margin:0;font-size:clamp(28px,7vw,38px);letter-spacing:-.05em;line-height:1.05}
.intro p:last-child{margin:12px 0 0;color:#8e97a6;font-size:14px;line-height:1.5}
.field{display:block;margin-top:14px}
.field span{display:block;margin-bottom:7px;color:#8e97a6;font-size:12px}
.field input{width:100%;height:45px;padding:0 14px;border:1px solid rgba(255,255,255,.08);border-radius:10px;outline:0;background:rgba(255,255,255,.035);color:#f4f5f7;transition:.2s}
.field input:focus{border-color:#f5b942;box-shadow:0 0 0 3px rgba(245,185,66,.13)}
.error{margin:12px 0 0;color:#f87171;font-size:12px}
.primary{width:100%;height:48px;margin-top:22px;border:0;border-radius:10px;background:#f5b942;color:#17191d;font-weight:800;cursor:pointer;transition:.2s}
.primary:hover{background:#ffd36d}
.primary:disabled{opacity:.6}
.switch{margin:22px 0 0;text-align:center;color:#8e97a6;font-size:12px}
.switch a{color:#f5b942;text-decoration:none}
</style>

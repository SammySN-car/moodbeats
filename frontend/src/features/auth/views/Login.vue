<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import client from '../../../api/client'

const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const showPassword = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const res = await client.post('/auth/login', {
      email: email.value,
      password: password.value
    })
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('userName', res.data.user_name)
    router.push('/')
  } catch (err) {
    error.value = err.response?.data?.detail || 'Login failed'
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
        <p class="eyebrow">WELCOME BACK</p>
        <h1>Find your next feeling.</h1>
        <p>Sign in to continue your personal sound journey.</p>
      </div>
      <form @submit.prevent="handleLogin">
        <label class="field">
          <span>Email</span>
          <input v-model.trim="email" type="email" autocomplete="email" placeholder="you@example.com" required />
        </label>
        <label class="field">
          <span>Password</span>
          <input v-if="showPassword" v-model="password" type="text" autocomplete="current-password" placeholder="Enter your password" required />
          <input v-else v-model="password" type="password" autocomplete="current-password" placeholder="Enter your password" required />
          <button v-if="password" class="peek" type="button" @click="showPassword = !showPassword">{{ showPassword ? 'Hide' : 'Show' }}</button>
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" type="submit" :disabled="loading">{{ loading ? 'Signing in...' : 'Sign in' }}</button>
      </form>
      <p class="switch">Don't have an account? <router-link to="/signup">Sign up</router-link></p>
    </section>
  </main>
</template>

<style scoped>
.auth-page{min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 50% 0,rgba(245,185,66,.13),transparent 42%),#0b0d10}
.auth-card{width:min(100%,430px);padding:32px;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(13,16,20,.76);box-shadow:0 20px 60px rgba(0,0,0,.22)}
.brand{display:flex;align-items:center;gap:9px;color:#f4f5f7;font-size:20px;font-weight:750;letter-spacing:-.04em;text-decoration:none}
.brand>span:last-child{color:#f5b942}
.mark{display:flex;align-items:end;gap:2px;height:22px}
.mark i{width:4px;border-radius:4px;background:#f5b942}
.mark i:nth-child(1){height:11px}
.mark i:nth-child(2){height:19px}
.mark i:nth-child(3){height:14px}
.intro{margin:48px 0 28px}
.eyebrow{margin:0 0 10px;color:#f5b942;font-size:10px;font-weight:800;letter-spacing:.15em}
.intro h1{margin:0;font-size:clamp(28px,7vw,38px);letter-spacing:-.05em;line-height:1.05}
.intro p:last-child{margin:12px 0 0;color:#8e97a6;font-size:14px;line-height:1.5}
.field{position:relative;display:block;margin-top:17px}
.field span{display:block;margin-bottom:8px;color:#8e97a6;font-size:12px}
.field input{width:100%;height:48px;padding:0 14px;border:1px solid rgba(255,255,255,.08);border-radius:10px;outline:0;background:rgba(255,255,255,.035);color:#f4f5f7;transition:.2s}
.field input:focus{border-color:#f5b942;box-shadow:0 0 0 3px rgba(245,185,66,.13)}
.peek{position:absolute;right:10px;bottom:8px;border:0;background:none;color:#8e97a6;font-size:11px;cursor:pointer}
.error{margin:12px 0 0;color:#f87171;font-size:12px}
.primary{width:100%;height:48px;margin-top:24px;border:0;border-radius:10px;background:#f5b942;color:#17191d;font-weight:800;cursor:pointer;transition:.2s}
.primary:hover{background:#ffd36d}
.primary:disabled{cursor:wait;opacity:.6}
.switch{margin:24px 0 0;text-align:center;color:#8e97a6;font-size:12px}
.switch a{color:#f5b942;text-decoration:none}
.switch a:hover{color:#ffd36d}
</style>

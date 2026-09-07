import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

import './shared/styles/variables.css'
import './shared/styles/base.css'
import './shared/styles/layout.css'
import './shared/styles/components.css'
import './shared/styles/animations.css'

createApp(App).use(router).mount('#app')

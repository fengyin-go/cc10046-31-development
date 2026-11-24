import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
import SampleLocatorView from '@/views/SampleLocatorView.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    { path: '/sample_locator', name: 'sample_locator', component: SampleLocatorView },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router

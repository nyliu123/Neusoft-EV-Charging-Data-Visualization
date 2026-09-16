import {createRouter, createWebHistory} from "vue-router";
import Dashboard from "../view/Dashboard.vue";
import Detail from "../view/Detail.vue";
import BusinessDetail from "../view/BusinessDetail.vue";

const router = createRouter({
    history:createWebHistory(),
    routes:[
        {
            path:'/',
            component:Dashboard
        },
        {
            path:'/details/:section(operations|stations|prediction|quality)',
            component:Detail
        },
        {
            path:'/details/:section(users|revenue)',
            component:BusinessDetail
        },
        {
            path:'/:pathMatch(.*)*',
            redirect:'/'
        }
    ],
    // #bottom 要等大屏数据渲染完高度才准，交给 Dashboard 自己滚；其余情况保持浏览器默认行为。
    scrollBehavior(to, from, savedPosition) {
        if (to.hash === '#bottom') return false
        if (to.hash) return { el: to.hash, behavior: 'smooth' }
        return savedPosition
    }
})

export default router;

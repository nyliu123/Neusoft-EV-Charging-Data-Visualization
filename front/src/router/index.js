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
    ]
})

export default router;

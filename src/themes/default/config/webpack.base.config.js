const path = require('path');

module.exports = {
    entry:{
        app: './app/app'
    },

    resolve: {
        extensions: ['.ts', '.js', '.json'],
        modules: ['./node_modules', './app'],
        alias: {
            'vue$': 'vue/dist/vue.common.js'
        }
    },

};
const path = require('path');
const merge = require('webpack-merge');
const common = require('./webpack.base.config');


const development = {
    devtool: 'cheap-inline-source-map',
    output:{
        filename: './[name].js',
        path: path.resolve(__dirname, '../assets/js'),
    }
};

module.exports = merge(common, development);
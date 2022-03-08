const path = require("path");

module.exports = {
	entry: {
		"js/application": "./static_src/js/application.js",
	},
	output: {
		filename: "[name].js",
		path: path.resolve(__dirname, "static"),
	},
	devtool: "source-map",
	resolve: {
		modules: ["node_modules", "static_src"],
		extensions: [".js"],
	}
};

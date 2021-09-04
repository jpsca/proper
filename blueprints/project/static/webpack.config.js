const path = require("path");

module.exports = {
	entry: {
		"js/scripts": "./src/js/scripts.js",
	},
	output: {
		filename: "[name].js",
		path: path.resolve(__dirname, "public"),
	},
	devtool: "source-map",
	resolve: {
		modules: ["node_modules", "src"],
		extensions: [".js", ".jsx"],
	}
};

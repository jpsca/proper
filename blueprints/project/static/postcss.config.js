const cssnano = require("cssnano");

module.exports = {
	plugins: [
		require("postcss-import"),
		require("@tailwindcss/jit")("./tailwind.config.js"),
		// require("tailwindcss")("./tailwind.config.js"),
		require("autoprefixer"),
		...process.env.NODE_ENV === "production"
			? [cssnano]
			: []
	]
};

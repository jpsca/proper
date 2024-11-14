// tailwind.config.js
module.exports = {
	content: [
		"app/views/**/*.jinja",
		"static_src/**/*.js",
	],
	plugins: [
		require("@tailwindcss/forms")({
			strategy: "class", // only generate classes
		}),
  ],
};

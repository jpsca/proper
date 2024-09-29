// tailwind.config.js
module.exports = {
	content: [
		"[[ app_name ]]/views/**/*.jinja",
		"static_src/**/*.js",
	],
	plugins: [
		require("@tailwindcss/forms")({
			strategy: "class", // only generate classes
		}),
  ],
};

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./public/index.html",
    "./src/renderer/**/*.{js,ts,jsx,tsx}",
    "./src/domain/**/*.{js,ts,jsx,tsx}",
    "./src/application/**/*.{js,ts,jsx,tsx}",
    "./src/infrastructure/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

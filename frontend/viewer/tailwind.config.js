/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Memory layer colors
        'layer-l0': '#ef4444', // red - identity_schema
        'layer-l1': '#f97316', // orange - active_context
        'layer-l2': '#eab308', // yellow - event_log
        'layer-l3': '#22c55e', // green - verified_fact
        'layer-l4': '#3b82f6', // blue - operational_knowledge
      },
    },
  },
  plugins: [],
}

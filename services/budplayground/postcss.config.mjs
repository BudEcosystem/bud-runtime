const isTest = Boolean(process.env.VITEST);

const config = {
  plugins: isTest ? [] : ["@tailwindcss/postcss"],
};

export default config;

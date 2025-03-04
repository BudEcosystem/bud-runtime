module.exports = {
  apps: [
    {
      name: "bud-serve-playground", // Change this to your app name
      script: "npm",
      args: "start",
      cwd: "./", // Change this to your actual Next.js project path
      instances: "1", // Run multiple instances (adjust as needed)
      exec_mode: "cluster",
      env: {
        NODE_ENV: "production",
        PORT: 7832, // Change this if needed
      },
    },
  ],
};

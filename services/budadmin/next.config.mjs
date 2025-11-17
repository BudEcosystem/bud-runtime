/** @type {import('next').NextConfig} */
import path from 'path';
import { config } from 'dotenv';
const __dirname = path.dirname(new URL(import.meta.url).pathname);

// Load environment variables from .env.local
config({
  path: path.resolve(__dirname, '.env.local'),
});

// eslint-disable-next-line import/no-anonymous-default-export
export default {
  sassOptions: {
    includePaths: [path.join(__dirname, 'styles')],
  },
  async rewrites() {
    return [
      {
        source: '/logIn',
        destination: '/auth/logIn',
      },
      {
        source: '/register',
        destination: '/auth/register',
      },
      {
        source: '/resetPassword',
        destination: '/auth/resetPassword',
      },
      {
        source: '/reset-password',
        destination: '/auth/reset-password',
      },
      {
        source: '/dashboard',
        destination: '/home/dashboard',
      },
      {
        source: '/projects',
        destination: '/home/projects',
      },
      {
        source: '/projects/:projectId/deployments/:deploymentId',
        // destination: '/home/projectId/deployments/[deploymentId]',
        destination: '/home/deployments/[deploymentId]',
      },
      {
        source: '/projects/:projectId',
        destination: '/home/projects/[projectId]',
      },
      {
        source: '/projects/:projectId/endpoint/:endpointId',
        destination: '/home/projects/[projectId]/endpoint/[endpointId]',
      },
      {
        source: '/projects/:projectId/endpoint/:endpointId/:scoreType',
        destination:
          '/home/projects/[projectId]/endpoint/[endpointId]/[scoreType]',
      },
      {
        source: '/projects/:projectId/deployments/:deploymentId/:scoreType',
        destination:
          // '/home/projects/[projectId]/PromptList',
          '/_commonPages/PromptList',
      },
      // {
      //   source: '/projects/:projectId/deployments/:deploymentId/PromptList',
      //   destination:
      //     '/home/projects/[projectId]/PromptList',
      // },
      {
        source: '/clusters',
        destination: '/home/clusters',
      },
      {
        source: '/clusters/:clustersId',
        destination: '/home/clusters/[clustersId]',
      },
      {
        source: '/clusters/:clustersId/deployments/:deploymentId',
        destination: '/home/deployments/[deploymentId]',
      },
      {
        source: '/clusters/:clustersId/deployments/:deploymentId/:scoreType',
        destination:
          '/_commonPages/PromptList',
          // '/home/clusters/[clustersId]/PromptList',
      },
      {
        source: '/clusters/:clustersId/perfomanceBenchmarks',
        destination: '/home/clusters/[clustersId]/PerfomanceBenchmarks',
      },
      {
        source: '/playground',
        destination: '/home/playground',
      },
      {
        source: '/modelRepo',
        destination: '/home/modelRepo',
      },
      {
        source: '/modelRepo/benchmarkHistory',
        destination: '/home/modelRepo/benchmarkHistory',
      },
      {
        source: '/modelRepo/benchmarkHistory/benchmarkResult',
        destination: '/home/modelRepo/benchmarkHistory/benchmarkResult',
      },

      {
        source: '/modelRepo/benchmarks-history',
        destination: '/home/_benchmarks',
      },
      {
        source: '/modelRepo/benchmarks-history/:benchmarkId',
        destination: '/home/_benchmarks/BenchmarkResult',
      },


      {
        source: '/settings',
        destination: '/home/settings',
      },
      {
        source: '/users',
        destination: '/home/userManagement',
      },
      {
        source: '/simulation',
        destination: '/home/simulations',
      },
      {
        source: '/help',
        destination: '/home/help',
      },
      {
        source: '/apiKeys',
        destination: '/home/apiKeys',
      },


      {
        source: '/evaluations',
        destination: '/home/evaluations',
      },
      {
        source: '/evaluations/:evaluationId',
        destination: '/home/evaluations/evalDetailed/[evaluationId]',
      },
      {
        source: '/guardrails',
        destination: '/home/guardrails',
      },

      {
        source: '/agents',
        destination: '/home/agents',
      },
    ];
  },
  env: {
    BASE_URL: process.env.NEXT_PUBLIC_BASE_URL,
  },
};

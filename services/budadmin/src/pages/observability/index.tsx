// Re-export the observability page component
export { default } from "../home/observability";

// Skip static generation — this page requires client-side rendering
export const getServerSideProps = () => ({ props: {} });

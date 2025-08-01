import { useEffect } from 'react';

export const useLoaderOnLoading = (isLoading: boolean) => {
  useEffect(() => {
    if (isLoading) {
      // Show loader logic here
      console.log('Loading started');
    } else {
      // Hide loader logic here
      console.log('Loading finished');
    }
  }, [isLoading]);
};

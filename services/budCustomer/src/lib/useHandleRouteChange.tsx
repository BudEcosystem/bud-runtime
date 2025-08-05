import { useEffect } from 'react';
import { useRouter } from 'next/router';

const useHandleRouteChange = (callback: () => void) => {
  const router = useRouter();

  useEffect(() => {
    const handleRouteChange = () => {
      callback();
    };

    router.events.on('routeChangeStart', handleRouteChange);
    router.events.on('routeChangeComplete', handleRouteChange);

    return () => {
      router.events.off('routeChangeStart', handleRouteChange);
      router.events.off('routeChangeComplete', handleRouteChange);
    };
  }, [router.events, callback]);
};

export default useHandleRouteChange;

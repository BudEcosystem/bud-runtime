import { ChevronLeftIcon, SlashIcon } from '@radix-ui/react-icons';
import { Flex } from '@radix-ui/themes';
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Text_14_400_5B6168, Text_14_400_965CDE } from '../ui/text';

type Props = {
  previousRoute?: string;
};

const routeNameMapping: { [key: string]: string } = {
  modelRepo: 'Models',
  benchmarkHistory: 'Benchmark history',
  benchmarkResult: 'Benchmark Result',
};
const Breadcrumb = ({ previousRoute }: Props) => {
  const [breadcrumbs, setBreadcrumbs] = useState<
    { href: string; text: string }[]
  >([]);
  const router = useRouter();

  useEffect(() => {
    const pathWithoutQuery = router.asPath.split('?')[0];
    const pathSegments = pathWithoutQuery
      .split('/')
      .filter((segment) => segment);
    const breadcrumbs = pathSegments.map((segment, index) => {
      const href = '/' + pathSegments.slice(0, index + 1).join('/');
      let text =
        routeNameMapping[segment] ||
        segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, ' ');
      return { href, text };
    });

    setBreadcrumbs(breadcrumbs);
  }, [router.asPath]);
  return (
    <div className="mb-8">
      <Flex className="px-[5.1%]" align="center">
        <Flex
          width="28px"
          height="28px"
          align="center"
          mr="3"
          className="rounded-full bg-[#18191B] justify-center"
        >
          <ChevronLeftIcon
            className="w-4 h-4"
            onClick={() => router.push(previousRoute)}
          />
        </Flex>
        {breadcrumbs.map((breadcrumb, index) => {
          let isActive = index === breadcrumbs.length - 1;
          return (
            <Flex align="center" key={index}>
              {isActive ? (
                <Text_14_400_965CDE
                  className="cursor-pointer"
                  onClick={() => router.push(breadcrumb.href)}
                >
                  {breadcrumb.text}
                </Text_14_400_965CDE>
              ) : (
                <>
                  <Text_14_400_5B6168
                    className="cursor-pointer"
                    onClick={() => router.push(breadcrumb.href)}
                  >
                    {breadcrumb.text}
                  </Text_14_400_5B6168>
                  <SlashIcon color="#8181815B" className="mx-1" />
                </>
              )}
            </Flex>
          );
        })}
      </Flex>
    </div>
  );
};

export default Breadcrumb;

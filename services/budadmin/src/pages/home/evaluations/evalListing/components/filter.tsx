import React, { useState, useRef, useEffect } from 'react';
import { Image } from "antd";
import { Text_10_400_EEEEEE } from '@/components/ui/text';


const HorizontalScrollFilter = ({
  filters,
  selectedFilters = [],
  onFilterClick = (filter) => console.log('Filter clicked:', filter)
}) => {
  const scrollContainerRef = useRef(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  // Check scroll position and update button states
  const checkScrollPosition = () => {
    if (scrollContainerRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 1);
    }
  };

  // Calculate the width of one filter element plus gap
  const getElementScrollWidth = () => {
    if (scrollContainerRef.current && scrollContainerRef.current.children.length > 0) {
      const firstChild = scrollContainerRef.current.children[0];
      const computedStyle = window.getComputedStyle(firstChild);
      const width = firstChild.offsetWidth;
      const marginRight = parseFloat(computedStyle.marginRight) || 0;
      const gap = 4; // 0.1rem converted to px (assuming 1rem = 16px)
      return width + gap;
    }
    return 100; // fallback width
  };

  // Scroll left by one element
  const scrollLeft = () => {
    if (scrollContainerRef.current && canScrollLeft) {
      const scrollAmount = getElementScrollWidth();
      scrollContainerRef.current.scrollBy({
        left: -scrollAmount,
        behavior: 'smooth'
      });
    }
  };

  // Scroll right by one element
  const scrollRight = () => {
    if (scrollContainerRef.current && canScrollRight) {
      const scrollAmount = getElementScrollWidth();
      scrollContainerRef.current.scrollBy({
        left: scrollAmount,
        behavior: 'smooth'
      });
    }
  };

  // Handle filter click
  const handleFilterClick = (filter) => {
    onFilterClick(filter);
  };

  // Setup scroll listener
  useEffect(() => {
    console.log('filters', filters);
    const container = scrollContainerRef.current;
    if (container) {
      checkScrollPosition();
      container.addEventListener('scroll', checkScrollPosition);

      // Check on resize
      const handleResize = () => {
        setTimeout(checkScrollPosition, 100);
      };
      window.addEventListener('resize', handleResize);

      return () => {
        container.removeEventListener('scroll', checkScrollPosition);
        window.removeEventListener('resize', handleResize);
      };
    }
  }, [filters]);

  return (
    <div className="flex items-center gap-[.3rem] w-full justify-between">
      {/* Left Navigation Button */}
      <button
        className={`flex items-center justify-center w-[1.125rem] h-[1.125rem] rounded-full border border-white/5 backdrop-blur-[34.4px] transition-opacity ${canScrollLeft ? 'opacity-100 hover:bg-white/10' : 'opacity-30 cursor-not-allowed'
          }`}
        style={{ minWidth: 18, minHeight: 18 }}
        type="button"
        onClick={scrollLeft}
        disabled={!canScrollLeft}
      >
        <div className="flex justify-center h-[0.55rem] w-[auto]">
          <Image
            preview={false}
            className=""
            style={{ width: "auto", height: "0.55rem" }}
            src="/images/evaluations/icons/left.svg"
            alt="Logo"
          />
        </div>
      </button>

      {/* Scrollable Filter Container */}
      <div
        ref={scrollContainerRef}
        className="flex items-center justify-start gap-x-1 overflow-x-hidden scroll-smooth"
        style={{
          scrollbarWidth: 'none',
          msOverflowStyle: 'none'
        }}
        onScroll={checkScrollPosition}
      >
        {filters?.map((filter, index) => {
          const isSelected = selectedFilters.includes(filter);
          return (
            <button
              key={index}
              className={`px-[0.6rem] py-[0.2rem] rounded-[0.25rem] transition-all duration-200 whitespace-nowrap flex-shrink-0 ${
                isSelected
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : 'bg-[#1F1F1F] hover:bg-[#2F2F2F]'
              }`}
              onClick={() => handleFilterClick(filter)}
            >
              <Text_10_400_EEEEEE className='leading-[140%]'>{filter}</Text_10_400_EEEEEE>
            </button>
          );
        })}
      </div>

      {/* Right Navigation Button */}
      <button
        className={`flex items-center justify-center w-[1.125rem] h-[1.125rem] rounded-full border border-white/5 backdrop-blur-[34.4px]  transition-opacity ${canScrollRight ? 'opacity-100 hover:bg-white/10' : 'opacity-30 cursor-not-allowed'
          }`}
        style={{ minWidth: 18, minHeight: 18 }}
        type="button"
        onClick={scrollRight}
        disabled={!canScrollRight}
      >
        <div className="flex justify-center h-[0.55rem] w-[auto]">
          <Image
            preview={false}
            className=""
            style={{ width: "auto", height: "0.55rem" }}
            src="/images/evaluations/icons/right.svg"
            alt="Logo"
          />
        </div>
      </button>

      <style jsx>{`
        .scroll-smooth::-webkit-scrollbar {
          display: none;
        }
      `}</style>
    </div>
  );
};

export default HorizontalScrollFilter;

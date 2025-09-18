import React, { useContext, useMemo, useRef, useState } from "react";
import { Avatar, Form, FormRule, Select, Spin } from "antd";
import debounce from "lodash/debounce";
import FloatLabel from "./FloatLabel";
import InfoLabel from "./InfoLabel";

export function DebounceSelect({
  fetchOptions,
  debounceTimeout = 800,
  ...props
}) {
  const [fetching, setFetching] = useState(false);
  const [options, setOptions] = useState([]);
  const fetchRef = useRef(0);
  const debounceFetcher = useMemo(() => {
    const loadOptions = (value) => {
      fetchRef.current += 1;
      const fetchId = fetchRef.current;
      setOptions([]);
      setFetching(true);
      fetchOptions(value).then((newOptions) => {
        if (fetchId !== fetchRef.current) {
          // for fetch callback order
          return;
        }
        setOptions(newOptions);
        setFetching(false);
      });
    };
    return debounce(loadOptions, debounceTimeout);
  }, [fetchOptions, debounceTimeout]);
  return (
    <div className="floating-select pt-[1.5rem]">
      <FloatLabel label={<InfoLabel text="Invite" />}>
        <Select
          labelInValue
          filterOption={false}
          onSearch={debounceFetcher}
          notFoundContent={fetching ? <Spin size="small" /> : null}
          onChange={(value) => {}}
          mode="tags"
          {...props}
          options={options}
        />
      </FloatLabel>
    </div>
  );
}

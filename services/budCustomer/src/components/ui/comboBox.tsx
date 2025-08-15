import * as Ariakit from "@ariakit/react";
import { matchSorter } from "match-sorter";
import { startTransition, useMemo, useState } from "react";

export default function ComboBox() {
  const list = [
    "Apple",
    "Bacon",
    "Banana",
    "Broccoli",
    "Burger",
    "Cake",
    "Candy",
    "Carrot",
    "Cherry",
    "Chocolate",
    "Cookie",
    "Cucumber",
    "Donut",
    "Fish",
    "Fries",
    "Grape",
    "Green apple",
    "Hot dog",
    "Ice cream",
    "Kiwi",
    "Lemon",
    "Lollipop",
    "Onion",
    "Orange",
    "Pasta",
    "Pineapple",
    "Pizza",
    "Potato",
    "Salad",
    "Sandwich",
    "Steak",
    "Strawberry",
    "Tomato",
    "Watermelon",
  ];
  const [searchValue, setSearchValue] = useState("");
  const matches = useMemo(() => matchSorter(list, searchValue), [searchValue]);
  return (
    <Ariakit.ComboboxProvider
      setValue={(value) => {
        startTransition(() => setSearchValue(value));
      }}
    >
      {/* <Ariakit.ComboboxLabel className="label w-full">
        Your favorite food
      </Ariakit.ComboboxLabel> */}
      <Ariakit.Combobox
        placeholder="e.g., Apple"
        className="w-full place max-w-[350px] text-[0.740625rem] font-light text-[#44474D] h-[1.75rem] content-center	 bg-[#0f0f0f] outline-[white] rounded-md border border-[#212225] shadow-none bg-transparent leading-[100%] pt-[.2em] !border-[.5px] hover:border-[#63656c] px-[.3rem]"
      />
      <Ariakit.ComboboxPopover gutter={8} sameWidth className="popover">
        {matches.length ? (
          matches.map((value) => (
            <Ariakit.ComboboxItem
              key={value}
              value={value}
              className="combobox-item"
            />
          ))
        ) : (
          <div className="no-results">No results found</div>
        )}
      </Ariakit.ComboboxPopover>
    </Ariakit.ComboboxProvider>
  );
}

import React from 'react'
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import { Tag } from '../dataEntry/TagsInput';
import { PrimaryButton } from '../form/Buttons';
import { Flex } from 'antd';
import Tags from 'src/flows/components/DrawerTags';

function ModelFilter({
    search,
    setSearch,
    buttonLabel,
    onButtonClick,
    selectedTags = [],
    setSelectedTags,
    filterClick,
    buttonPermission
}: {
    search: string;
    setSearch: (value: string) => void;
    buttonLabel?: string;
    onButtonClick?: () => void;
    selectedTags?: Tag[];
    setSelectedTags?: (value: Tag[]) => void;
    filterClick?: () => void;
    buttonPermission?: boolean;
}) {
    return (
        <div className="px-[1.4rem] py-[1.8rem] rounded-es-lg rounded-ee-lg pb-[.5rem]">
            <div className="flex items-center justify-between gap-[0.625rem]">
                <SearchHeaderInput
                    placeholder="Model names, Tags, Tasks, Parameter sizes"
                    searchValue={search}
                    expanded
                    setSearchValue={setSearch}
                    classNames="border border-[.5px] border-[#757575]"
                />
                {buttonLabel && <PrimaryButton classNames="!min-w-[107px] !px-[1.5rem]"
                    onClick={onButtonClick}
                    text={buttonLabel}
                    permission={buttonPermission}
                >
                </PrimaryButton>}
                {filterClick&&<div onClick={filterClick} className="cursor-pointer">
                    <svg width="1rem" height="1rem" viewBox="0 0 14 15" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path fillRule="evenodd" clipRule="evenodd" d="M5.13324 3.33594C4.37845 3.33594 3.76657 3.94782 3.76657 4.7026C3.76657 5.45739 4.37845 6.06927 5.13324 6.06927C5.88803 6.06927 6.4999 5.45739 6.4999 4.7026C6.4999 3.94782 5.88803 3.33594 5.13324 3.33594ZM2.7999 5.2026C2.80643 5.2026 2.81293 5.20248 2.8194 5.20223C3.04873 6.26936 3.99757 7.06927 5.13324 7.06927C6.2689 7.06927 7.21774 6.26936 7.44707 5.20223C7.45354 5.20248 7.46004 5.2026 7.46657 5.2026H12.5999C12.876 5.2026 13.0999 4.97875 13.0999 4.7026C13.0999 4.42646 12.876 4.2026 12.5999 4.2026H7.46657C7.46004 4.2026 7.45354 4.20273 7.44707 4.20298C7.21774 3.13584 6.2689 2.33594 5.13324 2.33594C3.99757 2.33594 3.04873 3.13584 2.8194 4.20298C2.81293 4.20273 2.80643 4.2026 2.7999 4.2026H1.3999C1.12376 4.2026 0.899902 4.42646 0.899902 4.7026C0.899902 4.97875 1.12376 5.2026 1.3999 5.2026H2.7999ZM11.1804 10.8022C10.9511 11.8694 10.0022 12.6693 8.86657 12.6693C7.7309 12.6693 6.78207 11.8694 6.55274 10.8022C6.54627 10.8025 6.53977 10.8026 6.53324 10.8026H1.3999C1.12376 10.8026 0.899902 10.5787 0.899902 10.3026C0.899902 10.0265 1.12376 9.8026 1.3999 9.8026H6.53324C6.53977 9.8026 6.54627 9.80273 6.55274 9.80298C6.78207 8.73584 7.7309 7.93594 8.86657 7.93594C10.0022 7.93594 10.9511 8.73584 11.1804 9.80298C11.1869 9.80273 11.1934 9.8026 11.1999 9.8026H12.5999C12.876 9.8026 13.0999 10.0265 13.0999 10.3026C13.0999 10.5787 12.876 10.8026 12.5999 10.8026H11.1999C11.1934 10.8026 11.1869 10.8025 11.1804 10.8022ZM7.4999 10.3026C7.4999 9.54782 8.11178 8.93594 8.86657 8.93594C9.62136 8.93594 10.2332 9.54782 10.2332 10.3026C10.2332 11.0574 9.62136 11.6693 8.86657 11.6693C8.11178 11.6693 7.4999 11.0574 7.4999 10.3026Z" fill="#C7C7C7" />
                    </svg>
                </div>}
            </div>
            <div className="mt-6 mb-[1rem]">
                <Flex gap="4px 0" wrap>
                    {selectedTags
                        ?.sort((a, b) => a.name.localeCompare(b.name))
                        .map((tag, index) => (
                            <Tags
                                name={tag.name}
                                color={tag.color}
                                key={index}
                                closable={selectedTags?.find((selectedTag) => selectedTag.name === tag.name).name !== undefined}
                                onClose={() => {
                                    setSelectedTags(selectedTags.filter((selectedTag) => selectedTag.name !== tag.name));
                                }}
                                onClick={() => {
                                    if (selectedTags.includes(tag)) {
                                        setSelectedTags(selectedTags.filter((selectedTag) => selectedTag !== tag));
                                    }
                                    else {
                                        setSelectedTags([...selectedTags, tag]);
                                    }
                                }}
                                classNames='flex'
                            />
                        ))}
                </Flex>
            </div>

        </div>
    )
}

export default ModelFilter
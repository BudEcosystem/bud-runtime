import React, { useEffect, useState } from 'react';
import { Button, Table, notification } from 'antd';
import ProjectTags from 'src/flows/components/ProjectTags';
import { BorderlessButton, PrimaryButton } from '../form/Buttons';
import { useRouter } from "next/router";
import { useDrawer } from 'src/hooks/useDrawer';
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_16_600_FFFFFF } from '../../text';
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import { usePrompts } from "src/hooks/usePrompts";
import { formatDate } from 'src/utils/formatDate';
import NoDataFount from '../../noDataFount';
import useHandleRouteChange from '@/lib/useHandleRouteChange';
import { PermissionEnum, useUser } from 'src/stores/useUser';
import { endpointStatusMapping } from '@/lib/colorMapping';
import { errorToast, successToast } from '@/components/toast';
import { SortIcon } from './SortIcon';
import { useConfirmAction } from 'src/hooks/useConfirmAction';
import { useLoaderOnLoding } from 'src/hooks/useLoaderOnLoading';
import { IconOnlyRender } from 'src/flows/components/BudIconRender';
import { useEndPoints } from 'src/hooks/useEndPoint';

const capitalize = (str: string) => str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

const formatPromptType = (text: string) => {
    if (!text) return '';
    // Replace underscores, hyphens, and other special characters with spaces
    return text
        .replace(/[_-]/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
};

interface DataType {
    key?: string;
    id?: string;
    name?: string;
    version?: string;
    default_version?: string;
    prompt_type?: string;
    status?: string;
    model_name?: string;
    modality?: string[];
    created_at?: string;
    model?: any;
}

function AgentsPromptsListTable() {
    const [isMounted, setIsMounted] = useState(false);
    const [confirmLoading, setConfirmLoading] = useState(false);
    const { openDrawer } = useDrawer();
    const [searchValue, setSearchValue] = useState('');
    const router = useRouter();
    const { projectId } = router.query;
    const { prompts, getPrompts, deletePrompt, loading } = usePrompts();
    const [order, setOrder] = useState<'-' | ''>('-');
    const [orderBy, setOrderBy] = useState<string>('created_at');
    const { hasProjectPermission, hasPermission } = useUser();
    const { getEndpointClusterDetails } = useEndPoints();
    useLoaderOnLoding(loading);
    const { contextHolder, openConfirm } = useConfirmAction();
    const [confirmVisible, setConfirmVisible] = useState(false);

    const page = 1;
    const limit = 1000;

    const getData = async () => {
        getPrompts({
            page: page,
            limit: limit,
            name: searchValue,
            order_by: `${order}${orderBy}`,
            project_id: projectId as string,
        }, projectId as string);
    };

    useHandleRouteChange(() => {
        notification.destroy();
    });

    useEffect(() => {
        if (projectId) {
            getData();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [projectId]);

    useEffect(() => {
        if (!projectId) return;

        const timer = setTimeout(() => {
            getPrompts({
                page: page,
                limit: limit,
                name: searchValue,
                order_by: `${order}${orderBy}`,
                project_id: projectId as string,
            }, projectId as string);
        }, 500);
        return () => clearTimeout(timer);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchValue, order, orderBy]);

    const confirmDelete = (record: DataType) => {
        if (record?.status === 'deleting' || record?.status === 'deleted') {
            errorToast('Prompt is in deleting state, please wait for it to complete');
            return;
        }
        setConfirmVisible(true);
        openConfirm({
            message: `You're about to delete the ${record?.name} prompt`,
            description: 'Once you delete the prompt, it will not be recovered. Are you sure?',
            cancelAction: () => {},
            cancelText: 'Cancel',
            loading: confirmLoading,
            key: 'delete-prompt',
            okAction: async () => {
                if (!record) {
                    errorToast('No record selected');
                    return;
                }
                setConfirmLoading(true);
                try {
                    await deletePrompt(record?.id, projectId as string);
                    await getData();
                    successToast('Prompt deleted successfully');
                } catch (error) {
                    errorToast('Failed to delete prompt');
                }
                setConfirmLoading(false);
                setConfirmVisible(false);
            },
            okText: 'Delete',
            type: 'warining'
        });
    };

    useEffect(() => {
        setIsMounted(true);
    }, [router.isReady]);

    return (
        <div className='pb-[60px] pt-[.4rem]'>
            {contextHolder}
            {isMounted && (
                <Table<DataType>
                    columns={[
                        {
                            title: 'Prompt Name',
                            dataIndex: 'name',
                            key: 'name',
                            render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
                            sortOrder: orderBy === 'name' ? order === '-' ? 'descend' : 'ascend' : undefined,
                            sorter: true,
                            sortIcon: SortIcon,
                        },
                        {
                            title: 'Version',
                            dataIndex: 'default_version',
                            key: 'default_version',
                            render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
                            sortIcon: SortIcon,
                        },
                        {
                            title: 'Type',
                            dataIndex: 'prompt_type',
                            key: 'prompt_type',
                            render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{formatPromptType(text)}</Text_12_400_EEEEEE>,
                            sortIcon: SortIcon,
                        },
                        {
                            title: 'Status',
                            key: 'status',
                            dataIndex: 'status',
                            sortOrder: orderBy === 'status' ? order === '-' ? 'descend' : 'ascend' : undefined,
                            sorter: true,
                            render: (status) => (
                                <span>
                                    <ProjectTags
                                        name={capitalize(status)}
                                        color={endpointStatusMapping[capitalize(status)]}
                                        textClass="text-[.75rem]"
                                    />
                                </span>
                            ),
                            sortIcon: SortIcon,
                        },
                        {
                            title: 'Model Name',
                            dataIndex: 'model',
                            key: 'model_name',
                            width: 150,
                            render: (model, record) => {
                                if (model) {
                                    return (
                                        <div className='select-none flex items-center'>
                                            <div className='w-[0.875rem] h-[0.875rem]'>
                                                <IconOnlyRender
                                                    icon={model.icon}
                                                    model={model}
                                                    type={model.provider_type}
                                                    imageSize={14}
                                                />
                                            </div>
                                            <Text_12_300_EEEEEE
                                                className='flex-auto truncate max-w-[90%]'
                                                style={{ marginLeft: 10 }}
                                            >
                                                {model?.name}
                                            </Text_12_300_EEEEEE>
                                        </div>
                                    );
                                }
                                return <Text_12_400_EEEEEE>{record.model_name || '-'}</Text_12_400_EEEEEE>;
                            },
                            sortIcon: SortIcon,
                        },
                        {
                            title: 'Modality',
                            dataIndex: 'modality',
                            key: 'modality',
                            render: (modalities: string[]) => {
                                if (!modalities || modalities.length === 0) return <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>;
                                const formattedModalities = modalities.map(m => formatPromptType(m)).join(', ');
                                return <Text_12_400_EEEEEE className='whitespace-nowrap max-w-[150px] truncate'>{formattedModalities}</Text_12_400_EEEEEE>;
                            },
                            sortIcon: SortIcon,
                        },
                        {
                            title: 'Created On',
                            dataIndex: 'created_at',
                            sorter: true,
                            key: 'created_at',
                            sortOrder: orderBy === 'created_at' ? order === '-' ? 'descend' : 'ascend' : undefined,
                            render: (text) => <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>,
                            sortIcon: SortIcon,
                        },
                        {
                            title: '',
                            dataIndex: 'actions',
                            key: 'actions',
                            render: (_text, record) => (
                                <div className='min-w-[100px]'>
                                    <div className='flex flex-row items-center justify-end'>
                                        <BorderlessButton
                                            permission={hasPermission(PermissionEnum.ModelManage)}
                                            onClick={async (event: React.MouseEvent) => {
                                                event.stopPropagation();
                                                await getEndpointClusterDetails(
                                                    record.id!,
                                                    projectId as string,
                                                );
                                                openDrawer("use-model", { endpoint: record });
                                            }}
                                        >
                                            Use this agent
                                        </BorderlessButton>
                                        {/* <div className='ml-[.3rem]'>
                                            <PrimaryButton
                                                classNames='rounded-[0.375rem]'
                                                permission={hasPermission(PermissionEnum.ProjectManage)}
                                                onClick={(event: React.MouseEvent) => {
                                                    event.stopPropagation();
                                                    // openDrawer('view-prompt', { prompt: record });
                                                }}
                                            >
                                                View
                                            </PrimaryButton>
                                        </div> */}
                                        <div className='ml-[.3rem] w-[1rem] h-auto block'>
                                            <Button
                                                className='bg-transparent border-none p-0 opacity-0 group-hover:opacity-100'
                                                onClick={(event: React.MouseEvent) => {
                                                    event.stopPropagation();
                                                    if (!hasPermission(PermissionEnum.ProjectManage)) return;
                                                    confirmDelete(record);
                                                }}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 14 15" fill="none">
                                                    <path fillRule="evenodd" clipRule="evenodd" d="M5.13327 1.28906C4.85713 1.28906 4.63327 1.51292 4.63327 1.78906C4.63327 2.0652 4.85713 2.28906 5.13327 2.28906H8.8666C9.14274 2.28906 9.3666 2.0652 9.3666 1.78906C9.3666 1.51292 9.14274 1.28906 8.8666 1.28906H5.13327ZM2.7666 3.65573C2.7666 3.37959 2.99046 3.15573 3.2666 3.15573H10.7333C11.0094 3.15573 11.2333 3.37959 11.2333 3.65573C11.2333 3.93187 11.0094 4.15573 10.7333 4.15573H10.2661C10.2664 4.1668 10.2666 4.17791 10.2666 4.18906V11.5224C10.2666 12.0747 9.81889 12.5224 9.2666 12.5224H4.73327C4.18098 12.5224 3.73327 12.0747 3.73327 11.5224V4.18906C3.73327 4.17791 3.73345 4.1668 3.73381 4.15573H3.2666C2.99046 4.15573 2.7666 3.93187 2.7666 3.65573ZM9.2666 4.18906L4.73327 4.18906V11.5224L9.2666 11.5224V4.18906Z" fill="#B3B3B3" />
                                                </svg>
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            ),
                            sortIcon: SortIcon,
                        },
                    ]}
                    pagination={false}
                    dataSource={prompts}
                    bordered={false}
                    footer={null}
                    virtual
                    onRow={() => {
                        return {
                            className: 'group',
                        };
                    }}
                    onChange={(_pagination, _filters, sorter: any) => {
                        setOrder(sorter.order === 'ascend' ? '' : '-');
                        setOrderBy(sorter.field);
                    }}
                    showSorterTooltip={true}
                    title={() => (
                        <div className='flex justify-between items-center px-[0.75rem] py-[1rem]'>
                            <Text_16_600_FFFFFF className='text-[#EEEEEE]'>
                                Prompt List
                            </Text_16_600_FFFFFF>
                            <div className='flex items-center justify-between gap-x-[.8rem]'>
                                <SearchHeaderInput
                                    placeholder={'Search by name'}
                                    searchValue={searchValue}
                                    setSearchValue={setSearchValue}
                                />
                                {(hasPermission(PermissionEnum.ProjectManage) || hasProjectPermission(projectId as string, PermissionEnum.ProjectManage)) && (
                                    <PrimaryButton
                                        onClick={() => {
                                            // openDrawer("create-prompt");
                                        }}
                                    >
                                        <div className='flex items-center justify-center'>
                                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
                                                <path fillRule="evenodd" clipRule="evenodd" d="M6 1.5C6.27614 1.5 6.5 1.72386 6.5 2V6H10.5C10.7761 6 11 6.22386 11 6.5C11 6.77614 10.7761 7 10.5 7H6.5V11C6.5 11.2761 6.27614 11.5 6 11.5C5.72386 11.5 5.5 11.2761 5.5 11V7H1.5C1.22386 7 1 6.77614 1 6.5C1 6.22386 1.22386 6 1.5 6H5.5V2C5.5 1.72386 5.72386 1.5 6 1.5Z" fill="#EEEEEE" />
                                            </svg>
                                            <div className='ml-2' />
                                            Create New
                                        </div>
                                    </PrimaryButton>
                                )}
                            </div>
                        </div>
                    )}
                    locale={{
                        emptyText: (
                            <NoDataFount
                                classNames="h-[20vh]"
                                textMessage={`No prompts`}
                            />
                        ),
                    }}
                />
            )}
        </div>
    );
}

export default AgentsPromptsListTable;

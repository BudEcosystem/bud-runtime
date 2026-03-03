import React, { useEffect, useState } from 'react';
import { Button, Image, notification, Table } from 'antd';
import ProjectTags from 'src/flows/components/ProjectTags';
import { Model } from 'src/hooks/useModels';
import { Cluster } from 'src/hooks/useCluster';
import { assetBaseUrl } from '@/components/environment';
import { BorderlessButton, PrimaryButton, SecondaryButton } from '../form/Buttons';
import { useRouter as useRouter } from "next/router";
import { useDrawer } from 'src/hooks/useDrawer';
import { useDeployModel } from 'src/stores/useDeployModel';
import { useProjects } from 'src/hooks/useProjects';
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_16_600_FFFFFF } from '../../text';
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import { useEndPoints } from "src/hooks/useEndPoint";
import { formatDate } from 'src/utils/formatDate';
import { openWarning } from '@/components/warningMessage';
import NoDataFount from '../../noDataFount';
import useHandleRouteChange from '@/lib/useHandleRouteChange';
import { PermissionEnum, useUser } from 'src/stores/useUser';
import { endpointStatusMapping } from '@/lib/colorMapping';
import { errorToast, successToast } from '@/components/toast';
import { extractApiErrorMessage } from '@/utils/extractApiErrorMessage';
import { SortIcon } from './SortIcon';
import { useConfirmAction } from 'src/hooks/useConfirmAction';
import { useLoaderOnLoding } from 'src/hooks/useLoaderOnLoading';
import { IconOnlyRender } from 'src/flows/components/BudIconRender';
const capitalize = (str) => str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

interface DataType {
    key?: string;
    name?: string;
    status?: string;
    type?: string;
    created_at?: string;
    model?: Model;
    cluster?: Cluster;
    id?: string;
    is_published?: boolean;
    is_deprecated?: boolean;
}



function DeploymentListTable() {
    const [isMounted, setIsMounted] = useState(false);
    const [selectedRow, setSelectedRow] = useState<DataType | null>(null);
    const [confirmLoading, setConfirmLoading] = useState(false);
    const [confirmVisible, setConfirmVisible] = useState(false);
    const { reset } = useDeployModel();
    const { openDrawer } = useDrawer();
    const { getProject } = useProjects();
    const [searchValue, setSearchValue] = useState('');
    const router = useRouter()
    const { projectId } = router.query; // Access the dynamic part of the route
    const { endPoints, getEndPoints, deleteEndPoint, loading, getEndpointClusterDetails, setPageSource } = useEndPoints();
    const [order, setOrder] = useState<'-' | ''>('');
    const [orderBy, setOrderBy] = useState<string>('created_at');
    const { hasProjectPermission, hasPermission } = useUser();
    useLoaderOnLoding(loading);
    const { contextHolder, openConfirm } = useConfirmAction()

    const page = 1;
    const limit = 1000;
    const getData = async () => {
        await getProject(projectId as string)
        await getEndPoints({
            id: projectId as string,
            page: page,
            limit: limit,
            name: searchValue,
            order_by: `${order}${orderBy}`,
        })
    }
    const setEndpointDetails = (id, projectId) => {
        getEndpointClusterDetails(id, projectId);
    }

    useHandleRouteChange(() => {
        notification.destroy();
    });

    useEffect(() => {
        if (projectId) {
            getData();
        }
    }, [projectId])


    useEffect(() => {
        // debounce
        if (!projectId) return;

        const timer = setTimeout(() => {
            getEndPoints({
                id: projectId as string,
                page: page,
                limit: limit,
                name: searchValue,
                order_by: `${order}${orderBy}`,
            });
        }, 500);
        return () => clearTimeout(timer);
    }, [searchValue, order, orderBy]);

    const confirmDelete = (record) => {
        if (record?.status === 'deleting' || record?.status === 'deleted') {
            errorToast('Deployment is in deleting state, please wait for it to complete');
            return;
        }
        setSelectedRow(record);
        setConfirmVisible(true);
        openConfirm({
            message: `You're about to delete the ${record?.name} deployment`,
            description: 'Once you delete the deployment, it will not be recovered. If the deployment code is being used anywhere it wont function. Are you sure?',
            cancelAction: () => {
            },
            cancelText: 'Cancel',
            loading: confirmLoading,
            key: 'delete-endpoint',
            okAction: async () => {
                if (!record) {
                    errorToast('No record selected');
                    return;
                };
                setConfirmLoading(true);
                try {
                    const result = await deleteEndPoint(record?.id, projectId as string);
                    if (result?.data) {
                        await getData();
                        successToast('Deployment deleted successfully');
                    } else {
                        errorToast('Failed to delete deployment');
                    }
                } catch (error) {
                    errorToast(extractApiErrorMessage(error, 'Failed to delete deployment'));
                }
                await getData();
                setConfirmLoading(false);
                setConfirmVisible(false);
            },
            okText: 'Delete',
            type: 'warning'
        });
    }
    useEffect(() => {
        setIsMounted(true)
    }, [router.isReady]);

    return (
        <div className='pb-[60px] pt-[.4rem]'>
            {contextHolder}
            {isMounted && (
                <Table<DataType>
                    columns={[
                        {
                            title: 'Deployment Name',
                            dataIndex: 'name',
                            key: 'name',
                            render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
                            sortOrder: orderBy === 'name' ? order === '-' ? 'descend' : 'ascend' : undefined,
                            sorter: true,
                            sortIcon: SortIcon,
                        },
                        {
                            title: 'Model Name',
                            dataIndex: 'model',
                            key: 'model',
                            width: 150,
                            render: (text, record) => <div className='select-none flex items-center'>
                                <div className='w-[0.875rem] h-[0.875rem]'>
                                    <IconOnlyRender icon={text.icon} model={text} type={text.provider_type} imageSize={14} />
                                </div>
                                <Text_12_300_EEEEEE className='flex-auto truncate max-w-[90%]' style={{ marginLeft: 10 }}>{text?.name}</Text_12_300_EEEEEE>
                            </div>,
                            sortIcon: SortIcon,
                        },
                        {
                            title: 'Cluster Name',
                            dataIndex: 'cluster',
                            key: 'cluster_name',
                            render: (text) => <Text_12_400_EEEEEE>{text?.name}</Text_12_400_EEEEEE>,
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
                        // {
                        //     title: 'Type',
                        //     dataIndex: 'model',
                        //     key: 'type',
                        //     render: (text) => <Text_12_400_EEEEEE>nill</Text_12_400_EEEEEE>,
                        //     // render: (text) => <Text_12_400_EEEEEE>{text?.modality.toUpperCase()}</Text_12_400_EEEEEE>,
                        //     sortIcon: SortIcon,
                        // },
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
                            dataIndex: 'created_on',
                            key: 'created_on',
                            render: (text, record) => <div className='min-w-[130px]'>
                                <div className='flex flex-row items-center justify-end'>
                                    {!record.is_published ? (
                                        <BorderlessButton
                                            permission={hasPermission(PermissionEnum.ModelManage)}
                                            disabled={record.is_deprecated}
                                            onClick={async (event) => {
                                                event.stopPropagation();

                                                // Check if endpoint is deprecated
                                                if (record.is_deprecated) {
                                                    errorToast('Cannot publish deprecated endpoint');
                                                    return;
                                                }

                                                // Open the publish drawer with the endpoint details
                                                openDrawer('publish-endpoint', { endpoint: record });
                                            }}
                                        >
                                            {record.is_deprecated ? 'Deprecated' : 'Publish'}
                                        </BorderlessButton>
                                    ) : (
                                        <BorderlessButton
                                            permission={hasPermission(PermissionEnum.ModelManage)}
                                            onClick={async (event) => {
                                                event.stopPropagation();
                                                // await getEndpointClusterDetails(record.id, projectId as string);
                                                openDrawer('publish', { endpoint: record });
                                            }}
                                        >
                                            Publish Details
                                        </BorderlessButton>
                                    )}
                                    <BorderlessButton
                                        classNames='ml-[.3rem]'
                                        permission={hasPermission(PermissionEnum.ModelManage)}
                                        onClick={async (event) => {
                                            event.stopPropagation();
                                            await getEndpointClusterDetails(record.id, projectId as string);
                                            openDrawer('use-model', { endpoint: record });
                                        }}
                                    >
                                        Use this model
                                    </BorderlessButton>
                                    <div className='ml-[.3rem] w-[1rem] h-auto block'>
                                        <Button
                                            className='bg-transparent border-none p-0 opacity-0 group-hover:opacity-100'
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                if (!hasPermission(PermissionEnum.ModelManage)) return;
                                                confirmDelete(record)
                                            }}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 14 15" fill="none">
                                                <path fillRule="evenodd" clipRule="evenodd" d="M5.13327 1.28906C4.85713 1.28906 4.63327 1.51292 4.63327 1.78906C4.63327 2.0652 4.85713 2.28906 5.13327 2.28906H8.8666C9.14274 2.28906 9.3666 2.0652 9.3666 1.78906C9.3666 1.51292 9.14274 1.28906 8.8666 1.28906H5.13327ZM2.7666 3.65573C2.7666 3.37959 2.99046 3.15573 3.2666 3.15573H10.7333C11.0094 3.15573 11.2333 3.37959 11.2333 3.65573C11.2333 3.93187 11.0094 4.15573 10.7333 4.15573H10.2661C10.2664 4.1668 10.2666 4.17791 10.2666 4.18906V11.5224C10.2666 12.0747 9.81889 12.5224 9.2666 12.5224H4.73327C4.18098 12.5224 3.73327 12.0747 3.73327 11.5224V4.18906C3.73327 4.17791 3.73345 4.1668 3.73381 4.15573H3.2666C2.99046 4.15573 2.7666 3.93187 2.7666 3.65573ZM9.2666 4.18906L4.73327 4.18906V11.5224L9.2666 11.5224V4.18906Z" fill="#B3B3B3" />
                                            </svg>
                                        </Button>
                                    </div>
                                </div>
                            </div>,
                            sortIcon: SortIcon,
                        },
                    ]}
                    pagination={false}
                    dataSource={endPoints}
                    bordered={false}
                    footer={null}
                    virtual
                    onRow={(record, rowIndex) => {
                        return {
                            className: 'group',
                            onClick: async event => {
                                router.push(`/projects/${projectId}/deployments/${record.id}`)
                                setEndpointDetails(record.id, projectId as string);
                                setPageSource('Projects')
                            }
                        }
                    }}
                    onChange={(pagination, filters, sorter: {
                        order: 'ascend' | 'descend';
                        field: string;
                    }, extra) => {
                        setOrder(sorter.order === 'ascend' ? '' : '-')
                        setOrderBy(sorter.field)
                    }}
                    showSorterTooltip={true}

                    title={() => (
                        <div className='flex justify-between items-center px-[0.75rem] py-[1rem]'>
                            <Text_16_600_FFFFFF className='text-[#EEEEEE]'  >
                                Deployment List
                            </Text_16_600_FFFFFF>
                            <div className='flex items-center justify-between gap-x-[.8rem]'>
                                <SearchHeaderInput
                                    placeholder={'Search by name'}
                                    searchValue={searchValue}
                                    setSearchValue={setSearchValue}
                                />
                                {(hasPermission(PermissionEnum.ProjectManage) || hasProjectPermission(projectId as string, PermissionEnum.EndpointManage)) && <PrimaryButton
                                    onClick={() => {
                                        reset();
                                        openDrawer("deploy-model")
                                    }}
                                >
                                    <div className='flex items-center justify-center'>
                                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
                                            <path fillRule="evenodd" clipRule="evenodd" d="M5.48129 3.47747L6.12128 2.83745C6.63692 2.32183 7.54131 1.96401 8.44 1.83563C8.8829 1.77236 9.30173 1.76843 9.64357 1.81962C9.99743 1.87261 10.2143 1.9762 10.3156 2.07749C10.4169 2.17877 10.5205 2.39563 10.5735 2.74949C10.6247 3.09131 10.6207 3.51014 10.5575 3.95304C10.4291 4.85174 10.0712 5.75613 9.55559 6.27179L5.99843 9.82895L5.08127 8.91179C4.92506 8.75558 4.67179 8.75558 4.51558 8.91179C4.35937 9.068 4.35937 9.32127 4.51558 9.47748L5.71559 10.6775C5.8718 10.8337 6.12507 10.8337 6.28128 10.6775L6.71902 10.2397L7.65543 11.8004C7.7188 11.906 7.8273 11.9766 7.94956 11.9916C8.07181 12.0067 8.19417 11.9646 8.28127 11.8775L9.88127 10.2775C9.9703 10.1884 10.0122 10.0627 9.99441 9.93806L9.6227 7.33606L10.1213 6.83747C10.8056 6.15309 11.2078 5.05747 11.3494 4.06617C11.4211 3.56407 11.4297 3.06541 11.3647 2.631C11.3014 2.20861 11.16 1.79048 10.8813 1.51179C10.6026 1.2331 10.1844 1.09169 9.76205 1.02844C9.32764 0.963385 8.82897 0.971945 8.32687 1.04367C7.33558 1.18527 6.23995 1.58743 5.55559 2.27177L5.05701 2.77037L2.45501 2.39866C2.33037 2.38085 2.20462 2.42277 2.1156 2.51179L0.515598 4.11179C0.428501 4.19889 0.386388 4.32126 0.401438 4.44351C0.416488 4.56576 0.487022 4.67426 0.592643 4.73763L2.15335 5.67405L1.71561 6.11179C1.64059 6.18681 1.59845 6.28855 1.59845 6.39463C1.59845 6.50072 1.64059 6.60246 1.71561 6.67748L2.91561 7.87748C3.07182 8.03369 3.32509 8.03369 3.4813 7.87748C3.63751 7.72127 3.63751 7.468 3.4813 7.31179L2.56414 6.39464L3.0813 5.87748L5.48129 3.47747ZM8.07784 10.9495L7.30211 9.65664L8.91559 8.04317L9.17416 9.85321L8.07784 10.9495ZM2.73645 5.09096L4.34991 3.47748L2.53986 3.2189L1.44354 4.31522L2.73645 5.09096ZM1.88128 8.67747C2.03749 8.52126 2.03749 8.26799 1.88128 8.11178C1.72507 7.95557 1.47181 7.95557 1.3156 8.11178L0.515598 8.91178C0.359388 9.06799 0.359388 9.32126 0.515598 9.47747C0.671808 9.63368 0.925074 9.63368 1.08128 9.47747L1.88128 8.67747ZM3.0813 9.87749C3.23751 9.72128 3.23752 9.46801 3.08131 9.3118C2.9251 9.15559 2.67183 9.15559 2.51562 9.31179L0.915601 10.9118C0.75939 11.068 0.759387 11.3213 0.915595 11.4775C1.0718 11.6337 1.32507 11.6337 1.48128 11.4775L3.0813 9.87749ZM4.28128 11.0775C4.43749 10.9213 4.43749 10.668 4.28128 10.5118C4.12507 10.3556 3.87181 10.3556 3.7156 10.5118L2.9156 11.3118C2.75939 11.468 2.75939 11.7213 2.9156 11.8775C3.07181 12.0337 3.32507 12.0337 3.48128 11.8775L4.28128 11.0775ZM7.59671 5.79498C8.14847 5.79498 8.59576 5.34769 8.59576 4.79593C8.59576 4.24417 8.14847 3.79688 7.59671 3.79688C7.04495 3.79688 6.59766 4.24417 6.59766 4.79593C6.59766 5.34769 7.04495 5.79498 7.59671 5.79498Z" fill="#EEEEEE" />
                                        </svg>
                                        <div className='ml-2' />
                                        Deploy Model
                                    </div>
                                </PrimaryButton>}
                            </div>
                        </div>
                    )}
                    locale={{
                        emptyText: (
                            <NoDataFount
                                classNames="h-[20vh]"
                                textMessage={`No deployments`}
                            />
                        ),
                    }}
                />
            )}
        </div>
    );
};

export default DeploymentListTable;

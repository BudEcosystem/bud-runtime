import React, { useEffect, useState } from 'react';
import { Image, Input, notification, Table } from 'antd';
import type { TableProps } from 'antd';
import ProjectTags from '@/flows/components/ProjectTags';
import { Model } from '@/hooks/useModels';
import { Cluster, useCluster } from '@/hooks/useCluster';
import { assetBaseUrl } from '@/components/environment';
import { PrimaryButton } from '../form/Buttons';
import { useRouter as useRouter } from "next/router";
import { useDrawer } from '@/hooks/useDrawer';
import { useDeployModel } from '@/stores/useDeployModel';
import { useProjects } from '@/hooks/useProjects';
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_16_600_FFFFFF } from '../../text';
import SearchHeaderInput from '@/flows/components/SearchHeaderInput';
import { formatDate } from '@/utils/formatDate';
import { useOverlay } from '@/context/overlayContext';
import NoDataFount from '../../noDataFount';
import useHandleRouteChange from '@/lib/useHandleRouteChange';
import Tags from '@/flows/components/DrawerTags';
import { useLoaderOnLoding } from '@/hooks/useLoaderOnLoading';
const statusMapping = {
    'available': '#3EC564',
    'not_available': '#EC7575',
}

const capitalize = (str) => str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();


type ColumnsType<T extends object> = TableProps<T>['columns'];
type TablePagination<T extends object> = NonNullable<Exclude<TableProps<T>['pagination'], boolean>>;
type TablePaginationPosition<T extends object> = NonNullable<
    TablePagination<T>['position']
>[number];

interface DataType {
    key?: string;
    name?: string;
    status?: string;
    type?: string;
    created_at?: string;
    model?: Model;
    cluster?: Cluster;
    id?: string;
}

function SortIcon({ sortOrder }: { sortOrder: string }) {
    return sortOrder ? sortOrder === 'descend' ?
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
            <path fillRule="evenodd" clipRule="evenodd" d="M6.00078 2.10938C6.27692 2.10938 6.50078 2.33324 6.50078 2.60938L6.50078 9.40223L8.84723 7.05578C9.04249 6.86052 9.35907 6.86052 9.55433 7.05578C9.7496 7.25104 9.7496 7.56763 9.55433 7.76289L6.35433 10.9629C6.15907 11.1582 5.84249 11.1582 5.64723 10.9629L2.44723 7.76289C2.25197 7.56763 2.25197 7.25104 2.44723 7.05578C2.64249 6.86052 2.95907 6.86052 3.15433 7.05578L5.50078 9.40223L5.50078 2.60938C5.50078 2.33324 5.72464 2.10938 6.00078 2.10938Z" fill="#B3B3B3" />
        </svg>
        : <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
            <path fillRule="evenodd" clipRule="evenodd" d="M6.00078 10.8906C6.27692 10.8906 6.50078 10.6668 6.50078 10.3906L6.50078 3.59773L8.84723 5.94418C9.04249 6.13944 9.35907 6.13944 9.55433 5.94418C9.7496 5.74892 9.7496 5.43233 9.55433 5.23707L6.35433 2.03707C6.15907 1.84181 5.84249 1.84181 5.64723 2.03707L2.44723 5.23707C2.25197 5.43233 2.25197 5.74892 2.44723 5.94418C2.64249 6.13944 2.95907 6.13944 3.15433 5.94418L5.50078 3.59773L5.50078 10.3906C5.50078 10.6668 5.72464 10.8906 6.00078 10.8906Z" fill="#B3B3B3" />
        </svg>
        : null;
}

function ClustersListTable() {
    const [loading, setLoading] = useState(false);
    const { reset } = useDeployModel();
    const { openDrawer } = useDrawer();
    const [searchValue, setSearchValue] = useState('');
    const router = useRouter()
    const { projectId } = router.query; // Access the dynamic part of the route
    const { projectClusters, getClusters } = useProjects();
    const { getClusterById } = useCluster();
    const [order, setOrder] = useState<'-' | ''>('');
    const [orderBy, setOrderBy] = useState<string>('created_at');
    useLoaderOnLoding(loading);

    useHandleRouteChange(() => {
        notification.destroy();
    });

    const getData = () => {
        if (!projectId) return;

        setLoading(true);
        getClusters(projectId as string).then(() => {
            setLoading(false);
        });
    }

    useEffect(() => {
        getData();
    }, [projectId]);

    useEffect(() => {
        // debounce
        if (!projectId) return;

        const timer = setTimeout(() => {
            getData();
        }, 500);
        return () => clearTimeout(timer);
    }, [searchValue, order, orderBy]);

    return (
        <div className='pb-[60px] pt-[.4rem]'>
            <Table<Cluster>
                columns={[
                    {
                        title: 'Cluster Name',
                        dataIndex: 'name',
                        key: 'name',
                        render: (text) => <Text_12_400_EEEEEE
                            className='text-nowrap'
                        >{text}</Text_12_400_EEEEEE>,
                        sortOrder: orderBy === 'name' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        sorter: true,
                        sortIcon: SortIcon,
                    },
                    {
                        title: 'No. of Deployments',
                        dataIndex: 'endpoint_count',
                        key: 'endpoint_count',
                        width: 150,
                        sortOrder: orderBy === 'endpoint_count' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        sorter: true,
                        render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
                        sortIcon: SortIcon,
                    },
                    {
                        title: 'Hardware Type',
                        dataIndex: 'hardware_type',
                        key: 'hardware_type',
                        sortOrder: orderBy === 'hardware' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        sorter: true,
                        render: (text) => <Text_12_400_EEEEEE>{text?.join(', ')?.toUpperCase()
                        }</Text_12_400_EEEEEE>,
                        sortIcon: SortIcon,
                    },
                    {
                        title: 'No. of Nodes',
                        dataIndex: 'node_count',
                        key: 'node_count',
                        sorter: true,
                        sortOrder: orderBy === 'node_count' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        width: 150,
                        render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
                        sortIcon: SortIcon,
                    },
                    {
                        title: 'No. of Workers',
                        dataIndex: 'worker_count',
                        key: 'worker_count',
                        sorter: true,
                        sortOrder: orderBy === 'worker_count' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        width: 150,
                        render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
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
                                    color={statusMapping[status]}
                                />
                            </span>
                        ),
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
                        dataIndex: 'created_on',
                        key: 'created_on',
                        render: (text, record) => <div className='min-w-[130px]'>
                            <div className='flex flex-row items-center visible-on-hover'>
                                <PrimaryButton
                                    onClick={async (event) => {
                                        event.stopPropagation();
                                        await getClusterById(record.id);
                                        router.push(`/clusters/${record.id}`)
                                    }}
                                >
                                    View Cluster
                                </PrimaryButton>
                            </div>
                        </div>,
                        sortIcon: SortIcon,
                    },
                ]}
                pagination={false}
                dataSource={projectClusters?.filter((cluster) => {
                    return cluster.name?.toLowerCase().includes(searchValue.toLowerCase())
                })}
                bordered={false}
                footer={null}
                virtual
                onRow={(record, rowIndex) => {
                    return {
                        onClick: async event => {
                            // router.push(`/projects/${projectId}/deployments/${record.id}`)
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
                            Cluster List
                        </Text_16_600_FFFFFF>
                        <div className='flex items-center justify-between gap-x-[.4rem]'>
                            <SearchHeaderInput
                                placeholder={'Search by name'}
                                searchValue={searchValue}
                                setSearchValue={setSearchValue}
                            />
                        </div>
                    </div>
                )}
                locale={{
                    emptyText: (
                        <NoDataFount
                            classNames="h-[20vh]"
                            textMessage={`No clusters found`}
                        />
                    ),
                }}
            />
        </div>
    );
};

export default ClustersListTable;



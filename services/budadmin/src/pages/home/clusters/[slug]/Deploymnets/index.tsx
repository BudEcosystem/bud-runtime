import React, { useEffect, useState } from 'react';
import { Image, Modal, notification, Popconfirm, Table } from 'antd';
import ProjectTags from 'src/flows/components/ProjectTags';
import { Model } from 'src/hooks/useModels';
import { Cluster, useCluster } from 'src/hooks/useCluster';
import { assetBaseUrl } from '@/components/environment';
import { useRouter as useRouter } from "next/router";
import { useDrawer } from 'src/hooks/useDrawer';
import { useDeployModel } from 'src/stores/useDeployModel';
import { useProjects } from 'src/hooks/useProjects';
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import { useEndPoints } from "src/hooks/useEndPoint";
import { formatDate } from 'src/utils/formatDate';
import { openWarning } from '@/components/warningMessage';
import { useOverlay } from 'src/context/overlayContext';
import useHandleRouteChange from '@/lib/useHandleRouteChange';
import { PermissionEnum, useUser } from 'src/stores/useUser';
import { endpointStatusMapping } from '@/lib/colorMapping';
import BudStepAlert from 'src/flows/components/BudStepAlert';
import { errorToast, successToast } from '@/components/toast';
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_16_600_FFFFFF } from '@/components/ui/text';
import { PrimaryButton } from '@/components/ui/bud/form/Buttons';
import NoDataFount from '@/components/ui/noDataFount';
import { useLoaderOnLoding } from 'src/hooks/useLoaderOnLoading';
import { useConfirmAction } from 'src/hooks/useConfirmAction';
const capitalize = (str) => str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

interface DataType {
    id?: string
    key?: string;
    name?: string;
    status?: string;
    created_at?: string;
    project_name?: string;
    model_name?: Model;
    active_workers?: Cluster;
    total_workers?: Cluster;
    roi?: string;
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

function DeploymentListTable() {
    const [confirmLoading, setConfirmLoading] = useState(false);
    const [confirmVisible, setConfirmVisible] = useState(false);
    const { reset } = useDeployModel();
    const { openDrawer } = useDrawer();
    const { getProject } = useProjects();
    const [searchValue, setSearchValue] = useState('');
    const router = useRouter()
    const { clustersId } = router.query; // Access the dynamic part of the route
    const { clusters, getClusters, setCluster, selectedCluster, loading, deleteCluster, setClusterValues, getClusterById, getClusterEndpoints, clusterEndpoints } = useCluster();
    const [order, setOrder] = useState<'-' | ''>('');
    const [orderBy, setOrderBy] = useState<string>('created_at');
    const { hasProjectPermission, hasPermission } = useUser();
    const { contextHolder, openConfirm } = useConfirmAction()
    const { getEndpointClusterDetails, setPageSource } = useEndPoints();
    const projectId = router.query.projectId as string
    useLoaderOnLoding(loading);

    const page = 1;
    const limit = 1000;
    const getData = async () => {
        const clusterId = Array.isArray(clustersId) ? clustersId[0] : clustersId;
        await getClusterEndpoints({
            clusterId: clusterId as string,
            page: page,
            limit: limit,
        })
    }

    const setEndpointDetails = (id) => {
        getEndpointClusterDetails(id, projectId)
    }

    useHandleRouteChange(() => {
        notification.destroy();
    });

    useEffect(() => {
        if (clustersId) {
            getData();
        }
    }, [clustersId])


    return (
        <div className='pb-[60px] pt-[.4rem]'>
            {contextHolder}
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
                        title: 'Status',
                        dataIndex: 'status',
                        key: 'model',
                        width: 150,
                        render: (text) =>
                            <span>
                                <ProjectTags
                                    name={capitalize(text)}
                                    color={endpointStatusMapping[capitalize(text)]}
                                />
                            </span>,
                        // <div className='select-none flex items-center'>
                        //     <div className='w-[0.875rem] h-[0.875rem]'>
                        //         <Image src={`${assetBaseUrl}${text.provider.icon}`} preview={false}
                        //             style={{ width: '0.875rem' }}
                        //         />
                        //     </div>
                        //     <Text_12_300_EEEEEE className='flex-auto truncate max-w-[90%]' style={{ marginLeft: 10 }}>{text.name}</Text_12_300_EEEEEE>
                        // </div>,
                        sorter: true,
                        sortIcon: SortIcon,
                    },
                    {
                        title: 'Created On',
                        dataIndex: 'created_at',
                        key: 'created_at',
                        sorter: true,
                        sortOrder: orderBy === 'text' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        render: (text) => <Text_12_400_EEEEEE className='text-nowrap'>{formatDate(text)}</Text_12_400_EEEEEE>,
                        sortIcon: SortIcon,
                    },
                    {
                        title: 'Project Name',
                        key: 'project',
                        dataIndex: 'project',
                        sortOrder: orderBy === 'text' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        sorter: true,
                        render: (text) => (
                            <Text_12_400_EEEEEE>{
                                text?.name
                            }</Text_12_400_EEEEEE>
                        ),
                        sortIcon: SortIcon,
                    },
                    {
                        title: 'Model Name',
                        dataIndex: 'model',
                        key: 'model',
                        sorter: true,
                        sortOrder: orderBy === 'text' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        render: (text, record) => <div className="flex">
                            <div className='w-[0.875rem] h-[0.875rem] mr-[.4rem]'>
                                <Image src={`${assetBaseUrl + text.icon}`} preview={false}
                                    style={{ width: '0.875rem' }}
                                />
                            </div>
                            <Text_12_400_EEEEEE className='text-nowrap max-w-[150px] truncate'>{text.name}</Text_12_400_EEEEEE>
                        </div>,
                        sortIcon: SortIcon,
                    },
                    {
                        title: 'Active vs Total Workers',
                        dataIndex: 'created_at',
                        sorter: true,
                        key: 'active_workers',
                        sortOrder: orderBy === 'created_at' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        render: (text, record) => <Text_12_400_EEEEEE>{record.active_workers}/{record.total_workers}</Text_12_400_EEEEEE>,
                        sortIcon: SortIcon,
                    },
                    {
                        title: 'ROI',
                        dataIndex: 'roi',
                        key: 'roi',
                        render: (text,) => <div className='min-w-[130px]'>
                            {text}
                        </div>,
                        sorter: true,
                        sortOrder: orderBy === 'text' ? order === '-' ? 'descend' : 'ascend' : undefined,
                        sortIcon: SortIcon,
                    },
                ]}
                pagination={false}
                dataSource={clusterEndpoints}
                bordered={false}
                footer={null}
                virtual
                onRow={(record, rowIndex) => {
                    return {
                        onClick: async event => {
                            // router.push(`/clusters/${clustersId}/perfomanceBenchmarks`)
                            router.push(`/clusters/${clustersId}/deployments/${record.id}`)
                            setEndpointDetails(record.id)
                            setPageSource('Clusters')
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


                locale={{
                    emptyText: (
                        <NoDataFount
                            classNames="h-[20vh]"
                            textMessage={`No deployments`}
                        />
                    ),
                }}
            />
        </div>
    );
};

export default DeploymentListTable;



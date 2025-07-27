import React, { useEffect, useState } from 'react';
import { ConfigProvider, Image, Form, Popover, Table, Slider, Spin } from 'antd';
import type { TableProps } from 'antd';
import { useRouter as useRouter } from "next/router";
import { useDrawer } from 'src/hooks/useDrawer';
import { useProjects } from 'src/hooks/useProjects';
import { Text_12_400_757575, Text_12_400_EEEEEE, Text_12_600_EEEEEE, Text_14_400_EEEEEE } from '@/components/ui/text';
import { PrimaryButton, SecondaryButton } from '@/components/ui/bud/form/Buttons';
import Tags from 'src/flows/components/DrawerTags';
import { MixerHorizontalIcon } from '@radix-ui/react-icons';
import CustomPopover from 'src/flows/components/customPopover';
import { IWorker, useWorkers } from 'src/hooks/useWorkers';
import CustomSelect from 'src/flows/components/CustomSelect';
import NoDataFount from '@/components/ui/noDataFount';
import { formatDate } from 'src/utils/formatDate';
import { formatTimeToHMS } from 'src/utils/formatTime';
import { useLoader } from 'src/context/appContext';
import { useLoaderOnLoding } from 'src/hooks/useLoaderOnLoading';
import { PermissionEnum, useUser } from 'src/stores/useUser';

type ColumnsType<T extends object> = TableProps<T>['columns'];
type TablePagination<T extends object> = NonNullable<Exclude<TableProps<T>['pagination'], boolean>>;
type TablePaginationPosition<T extends object> = NonNullable<
  TablePagination<T>['position']
>[number];


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

const columns: ColumnsType<IWorker> = [
  {
    title: 'Worker Name',
    dataIndex: 'name',
    key: 'name',
    render: (text) => <Text_12_600_EEEEEE className='whitespace-nowrap'>{text}</Text_12_600_EEEEEE>,
    sorter: (a, b) => a.name.localeCompare(b.name),
    sortIcon: SortIcon,
  },
  {
    title: 'Status',
    dataIndex: 'status',
    key: 'status',
    render: (text) => <Tags
      name={text}
      color="#D1B854"
    />,
    sorter: (a, b) => a.status.localeCompare(b.status),
    sortIcon: SortIcon,
  },
  {
    title: 'Node Name',
    dataIndex: 'node_name',
    key: 'node_name',
    render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{text}</Text_12_400_EEEEEE>,
    sorter: (a, b) => a.node_name.localeCompare(b.node_name),
    sortIcon: SortIcon,
  },
  {
    title: 'Utilization',
    key: 'utilization',
    dataIndex: 'utilization',
    render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
    sorter: (a, b) => a.utilization.localeCompare(b.utilization),
    sortIcon: SortIcon,
  },
  {
    title: 'Hardware Type',
    dataIndex: 'hardware',
    key: 'hardware',
    render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{text?.toUpperCase()}</Text_12_400_EEEEEE>,
    sorter: (a, b) => a.hardware.localeCompare(b.hardware),
    sortIcon: SortIcon,
  },
  {
    title: 'Uptime',
    dataIndex: 'uptime',
    key: 'uptime',
    render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{formatTimeToHMS(text)}</Text_12_400_EEEEEE>,
    sorter: (a, b) => new Date(a.uptime).getTime() - new Date(b.uptime).getTime(),
    sortIcon: SortIcon,
  },
  {
    title: 'Last Restart Date',
    dataIndex: 'last_restart_datetime',
    key: 'last_restart_date',
    render: (text) => <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>,
    sorter: (a, b) => new Date(a.last_restart_datetime).getTime() - new Date(b.last_restart_datetime).getTime(),
    sortIcon: SortIcon,
  },
  {
    title: 'Last Updated Date',
    dataIndex: 'last_updated_datetime',
    key: 'last_updated_date',
    render: (text) => <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>,
    sorter: (a, b) => new Date(a.last_updated_datetime).getTime() - new Date(b.last_updated_datetime).getTime(),
    sortIcon: SortIcon,
  },
  {
    title: 'Node IP',
    dataIndex: 'node_ip',
    key: 'node_ip',
    render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
    sortIcon: SortIcon,
  },
];


const statusOptions = [
  {
    value: 'Pending',
    label: 'PENDING',
  },
  {
    value: 'Running',
    label: 'RUNNING',
  },
  {
    value: 'Succeeded',
    label: 'SUCCEEDED',
  },
  {
    value: 'Failed',
    label: 'FAILED',
  },
  {
    value: 'Unknown',
    label: 'UNKNOWN',
  }
]

const hardwareOptions = [
  {
    value: 'cpu',
    label: 'CPU',
  },
  {
    value: 'gpu',
    label: 'GPU',
  },
  {
    value: 'hpu',
    label: 'HPU',
  }
]


function WorkersTable() {
  const { hasPermission, loadingUser } = useUser();
  const { openDrawer } = useDrawer();
  const router = useRouter()
  const { deploymentId } = router.query; // Access the dynamic part of the route
  const { workers, getWorker, getWorkers, loading } = useWorkers();
  const projectId = router.query.projectId as string
  useLoaderOnLoding(loading);
  const [tempFilter, setTempFilter] = useState<{
    status?: string;
    hardware?: string;
  }>({});
  const [filterOpen, setFilterOpen] = React.useState(false);

  useEffect(() => {
    getWorkers(deploymentId as string, tempFilter, projectId);
  }, [deploymentId, projectId])

  const applyFilter = () => {
    getWorkers(deploymentId as string, tempFilter, projectId);
    setFilterOpen(false);
  };
  const resetFilter = () => {
    setTempFilter({});
    setFilterOpen(false);
    getWorkers(deploymentId as string, tempFilter, projectId);
  };
  const handleOpenChange = (open) => {
    setFilterOpen(open);
  };



  const content = (
    // bg-[#161616]
    <div className='mt-[.55rem] border border-[1px] border-[#1F1F1F] rounded-[6px] bg-[#161616] max-w-[18.5rem]'>
      <div className="border-b-[1px] border-b-[#1F1F1F] p-[1.4rem] flex items-start justify-start flex-col gap-y-[.5rem]">
        <Text_14_400_EEEEEE>Filter</Text_14_400_EEEEEE>
        <Text_12_400_757575>Apply the following filters to find worker of your choice.</Text_12_400_757575>
      </div>
      <div className="w-full flex flex-col gap-size-20 px-[1.4rem] pb-[1.5rem] pt-[1.9rem] max-h-[14rem] overflow-y-auto">
        <CustomSelect
          name="Status"
          label="Status"
          info="select Status"
          placeholder="Select Status"
          selectOptions={statusOptions}
          value={tempFilter?.status || ''}
          onChange={(value) => {
            setTempFilter((prev) => ({ ...prev, status: value }));
          }}
        />

        <CustomSelect
          name="Hardware Type"
          label="Hardware Type"
          info="Select Hardware Type"
          placeholder="Select Hardware Type"
          selectOptions={hardwareOptions}
          value={tempFilter?.hardware || ''}
          onChange={(value) => {
            setTempFilter((prev) => ({ ...prev, hardware: value }));
          }}
        />

        <div className="flex items-center justify-between">
          <SecondaryButton
            type="submit"
            onClick={resetFilter}
            classNames="!px-[.8rem] tracking-[.02rem]"
          >
            Reset
          </SecondaryButton>
          <PrimaryButton
            type="submit"
            onClick={applyFilter}
            classNames="!px-[.8rem] tracking-[.02rem]"
          >
            Apply
          </PrimaryButton>
        </div>
      </div>
    </div>
  );


  return (
    <div className='relative'>
      <Table<IWorker>
        className="min-h-[400px]"
        columns={columns}
        pagination={false}
        dataSource={workers}
        footer={null}
        virtual
        onRow={(record, rowIndex) => {
          return {
            onClick: async event => {
              await getWorker(deploymentId as string, record.id, false, projectId);
              openDrawer("worker-details")
            }
          }
        }}
        showSorterTooltip={false}
        title={() => (
          <div className='flex justify-between items-center px-[0.75rem] py-[1rem]'>
            <div className='flex justify-start items-center gap-[.4rem]'>
              {/* <Tags
                name="Model Name"
                color="#D1B854"
              />
              <Tags
                name="Cluster Name"
                color="#D1B854"
              /> */}
            </div>
            <div className='flex items-center'>
              <div className='mr-[.2rem] filterPopup'>
                <ConfigProvider
                  theme={{
                    token: {
                      sizePopupArrow: 0,
                    },
                  }}
                  getPopupContainer={(trigger) => (trigger.parentNode as HTMLElement) || document.body}
                >
                  <Popover
                    open={filterOpen}
                    onOpenChange={handleOpenChange}
                    content={content}
                    title=""
                    trigger="click"
                    placement="bottomRight"
                  >
                    <MixerHorizontalIcon
                      style={{ width: '0.875rem', height: '0.875rem' }}
                      className="mr-2"
                    />
                  </Popover>
                </ConfigProvider>
              </div>
              {hasPermission(PermissionEnum.ModelManage) && (
                <PrimaryButton
                  onClick={() => {
                    openDrawer("add-worker")
                  }}
                >
                  <Text_12_600_EEEEEE className='flex items-center justify-center'>
                    Add Worker
                  </Text_12_600_EEEEEE>
                </PrimaryButton>
              )}
            </div>
          </div>
        )}
        locale={{
          emptyText: (
            <NoDataFount
              classNames="h-[20vh]"
              textMessage={`No workers`}
            />
          ),
        }}
      />
    </div>
  );
};

export default WorkersTable;

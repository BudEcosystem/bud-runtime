import React, { useEffect, useState } from 'react';
import { ConfigProvider, Image, Input, Form, Popover, Radio, Select, Space, Table, Tag, Typography, Slider } from 'antd';
import type { TableProps } from 'antd';
import DrawerTags from 'src/flows/components/DrawerTags';
import ProjectTags from 'src/flows/components/ProjectTags';
import { Model } from 'src/hooks/useModels';
import { Cluster } from 'src/hooks/useCluster';
import { assetBaseUrl } from '@/components/environment';
import { SearchOutlined } from '@ant-design/icons';
import { useRouter as useNavigation } from 'next/navigation';
import { useRouter as useRouter } from "next/router";
import { useDrawer } from 'src/hooks/useDrawer';
import { useDeployModel } from 'src/stores/useDeployModel';
import { useProjects } from 'src/hooks/useProjects';
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import { Text_12_300_EEEEEE, Text_12_400_757575, Text_12_400_EEEEEE, Text_12_600_EEEEEE, Text_14_400_EEEEEE, Text_16_600_FFFFFF } from '@/components/ui/text';
import { PrimaryButton, SecondaryButton } from '@/components/ui/bud/form/Buttons';
import Tags from 'src/flows/components/DrawerTags';
import { MixerHorizontalIcon } from '@radix-ui/react-icons';
import CustomPopover from 'src/flows/components/customPopover';
import CustomSelect from 'src/flows/components/CustomSelect';
import NoDataFount from '@/components/ui/noDataFount';
import ComingSoon from '@/components/ui/comingSoon';
import BenchmarksTable from 'src/pages/home/_benchmarks/components/BenchmarksTable';
const { Search } = Input;

const statusMapping = {
  'Not Started': '#EEEEEE',
  'Deploying': '#965CDE',
  'Deployment Failed': '#EC7575',
  'Running': '#479D5F',
  'Unhealthy': '#D1B854',
  'Deleting': '#ECAE75',
  'Not Found': '#42CACF',
  'Stopped': '#DE5CD1',
}


type ColumnsType<T extends object> = TableProps<T>['columns'];
type TablePagination<T extends object> = NonNullable<Exclude<TableProps<T>['pagination'], boolean>>;
type TablePaginationPosition<T extends object> = NonNullable<
  TablePagination<T>['position']
>[number];

interface DataType {
  key: string;
  name: string;
  status: string;
  workers: string;
  throughput: string;
  mean_ttft: string;
  mean_tpot: string;
  tokens: string;
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

const columns: ColumnsType<DataType> = [
  {
    title: 'Ran on',
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
    render: (text) => <div className='flex justify-start items-center'>
      <Tags
        name={text}
        color="#D1B854"
      />
    </div>,
    sorter: (a, b) => a.status.localeCompare(b.status),
    sortIcon: SortIcon,
  },
  {
    title: 'Workers',
    dataIndex: 'workers',
    key: 'workers',
    render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{text}</Text_12_400_EEEEEE>,
    sorter: (a, b) => a.workers.localeCompare(b.workers),
    sortIcon: SortIcon,
  },
  {
    title: 'Throughput',
    key: 'throughput',
    dataIndex: 'throughput',
    render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
    sorter: (a, b) => a.throughput.localeCompare(b.throughput),
    sortIcon: SortIcon,
  },
  {
    title: 'Mean TTFT',
    dataIndex: 'mean_ttft',
    key: 'mean_ttft',
    render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{text}</Text_12_400_EEEEEE>,
    sorter: (a, b) => a.mean_ttft.localeCompare(b.mean_ttft),
    sortIcon: SortIcon,
  },
  {
    title: 'Mean TPOT',
    dataIndex: 'mean_tpot',
    key: 'mean_tpot',
    render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{text}</Text_12_400_EEEEEE>,
    sorter: (a, b) => new Date(a.mean_tpot).getTime() - new Date(b.mean_tpot).getTime(),
    sortIcon: SortIcon,
  },
  {
    title: 'Tokens',
    dataIndex: 'tokens',
    key: 'tokens',
    render: (text) => <Text_12_600_EEEEEE className='whitespace-nowrap'>{text}</Text_12_600_EEEEEE>,
    sorter: (a, b) => new Date(a.tokens).getTime() - new Date(b.tokens).getTime(),
    sortIcon: SortIcon,
  },
];

const data: DataType[] = [
  {
    key: '1',
    name: '3rd July, 2024',
    status: 'Reasoning',
    workers: '12',
    throughput: '67',
    mean_ttft: '14s',
    mean_tpot: '2.3s',
    tokens: '127',
  },
  {
    key: '1',
    name: '3rd July, 2024',
    status: 'Reasoning',
    workers: '12',
    throughput: '67',
    mean_ttft: '14s',
    mean_tpot: '2.3s',
    tokens: '127',
  },
  {
    key: '1',
    name: '3rd July, 2024',
    status: 'Reasoning',
    workers: '12',
    throughput: '67',
    mean_ttft: '14s',
    mean_tpot: '2.3s',
    tokens: '127',
  },
  {
    key: '1',
    name: '3rd July, 2024',
    status: 'Reasoning',
    workers: '12',
    throughput: '67',
    mean_ttft: '14s',
    mean_tpot: '2.3s',
    tokens: '127',
  },
  {
    key: '1',
    name: '3rd July, 2024',
    status: 'Reasoning',
    workers: '12',
    throughput: '67',
    mean_ttft: '14s',
    mean_tpot: '2.3s',
    tokens: '127',
  },
  {
    key: '1',
    name: '3rd July, 2024',
    status: 'Reasoning',
    workers: '12',
    throughput: '67',
    mean_ttft: '14s',
    mean_tpot: '2.3s',
    tokens: '127',
  },
  {
    key: '1',
    name: '3rd July, 2024',
    status: 'Reasoning',
    workers: '12',
    throughput: '67',
    mean_ttft: '14s',
    mean_tpot: '2.3s',
    tokens: '127',
  },
  {
    key: '1',
    name: '3rd July, 2024',
    status: 'Reasoning',
    workers: '12',
    throughput: '67',
    mean_ttft: '14s',
    mean_tpot: '2.3s',
    tokens: '127',
  },
];

const applyFilter = () => {

};
const content = (
  // bg-[#161616]
  <div className='mt-[.55rem] border border-[1px] border-[#1F1F1F] rounded-[6px] bg-[#161616] max-w-[296px]'>
    <div className="border-b-[1px] border-b-[#1F1F1F] p-[1.4rem] flex items-start justify-start flex-col gap-y-[.5rem]">
      <Text_14_400_EEEEEE>Filter</Text_14_400_EEEEEE>
      <Text_12_400_757575>Apply the following filters to find worker of your choice.</Text_12_400_757575>
    </div>
    <div className="w-full flex flex-col gap-size-20 px-[1.4rem] pb-[1.5rem] pt-[1.9rem] max-h-[245px] overflow-y-auto">
      <CustomSelect
        name="Model"
        label="Model"
        info="select Model"
        placeholder="Select Model"
      />
      <CustomSelect
        name="Cluster"
        label="Cluster"
        info="select Cluster"
        placeholder="Select Cluster"
      />
      <CustomSelect
        name="Status"
        label="Status"
        info="select Status"
        placeholder="Select Status"
      />
      <Form.Item className='mb-[0]'>
        <Text_12_400_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 text-nowrap">
          Throughput
          <CustomPopover title="Throughput from start to end." >
            <Image
              preview={false}
              src="/images/info.png"
              alt="info"
              style={{ width: '.75rem', height: '.75rem' }}
            />
          </CustomPopover>
        </Text_12_400_EEEEEE>
        <div className="flex items-center justify-center mt-[.8rem]">
          <div className="text-[#757575] text-[.75rem] h-[4px] mr-1 leading-8">0</div>
          <Slider
            className="budSlider mt-[2rem] w-full"
            min={5}
            max={100}
            step={1}
            value={[33, 45]}
            onChange={(value) => {
              null
            }}
            range={{ editable: true, minCount: 1, maxCount: 2 }}
            tooltip={{
              open: true,
              getPopupContainer: trigger => (trigger.parentNode as HTMLElement) || document.body,  // Cast parentNode to HTMLElement
            }}
            styles={{
              track: {
                backgroundColor: "#965CDE",
              },
              rail: {
                backgroundColor: "#212225",
                height: 4,
              },
            }}
          />
          <div className="text-[#757575] text-[.75rem] h-[4px] ml-1 leading-8">100</div>
        </div>
      </Form.Item>
      <Form.Item className='mb-[0]'>
        <Text_12_400_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 text-nowrap">
          Latency
          <CustomPopover title="Latency from start to end." >
            <Image
              preview={false}
              src="/images/info.png"
              alt="info"
              style={{ width: '.75rem', height: '.75rem' }}
            />
          </CustomPopover>
        </Text_12_400_EEEEEE>
        <div className="flex items-center justify-center mt-[.8rem]">
          <div className="text-[#757575] text-[.75rem] h-[4px] mr-1 leading-8">0</div>
          <Slider
            className="budSlider mt-[2rem] w-full"
            min={5}
            max={100}
            step={1}
            value={[33, 45]}
            onChange={(value) => {
              null
            }}
            range={{ editable: true, minCount: 1, maxCount: 2 }}
            tooltip={{
              open: true,
              getPopupContainer: trigger => (trigger.parentNode as HTMLElement) || document.body,  // Cast parentNode to HTMLElement
            }}
            styles={{
              track: {
                backgroundColor: "#965CDE",
              },
              rail: {
                backgroundColor: "#212225",
                height: 4,
              },
            }}
          />
          <div className="text-[#757575] text-[.75rem] h-[4px] ml-1 leading-8">100</div>
        </div>
      </Form.Item>
      <div className="flex items-center justify-between">
        <SecondaryButton
          type="submit"
          onClick={applyFilter}
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

function BenchmarkTable() {
  const { openDrawer } = useDrawer();
  const { getProject } = useProjects();
  const [showSearch, setShowSearch] = useState(false);
  const [searchValue, setSearchValue] = useState('');
  const router = useRouter()
  const { projectId } = router.query; // Access the dynamic part of the route
  const { openDrawerWithStep } = useDrawer();

  useEffect(() => {
    getProject(projectId as string)
    // openDrawerWithStep("use-model");

  }, [projectId])

  return (
    <div className='relative'>
      <div>
          <BenchmarksTable showTableTitle={true}/>
        </div>
    </div>
  );
};

export default BenchmarkTable;

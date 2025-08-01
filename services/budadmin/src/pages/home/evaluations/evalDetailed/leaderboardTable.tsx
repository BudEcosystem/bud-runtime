import React, { useEffect, useState } from 'react';
import { Image, Modal, notification, Popconfirm, Table } from 'antd';

import { useRouter as useRouter } from "next/router";


import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_16_600_FFFFFF } from '@/components/ui/text';
import NoDataFount from '@/components/ui/noDataFount';

import { SortIcon } from '@/components/ui/bud/table/SortIcon';
import { color } from 'echarts';
import Tags from 'src/flows/components/DrawerTags';
const capitalize = (str) => str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();



interface DataType {
  rank?: {
    name: string;
    color: string;
  };
  model: {
    icon: string,
    name: string
  }
  score?: string;
  lastUpdated?: string;
}

const sampleResponse = [
  {
    rank: { name: '#1', color: '#965CDE' },
    model: { icon: '/images/drawer/zephyr.png', name: 'GPT 3.5' },
    score: '65.1',
    lastUpdated: '2 days ago'
  },
  {
    rank: { name: '#2', color: '#42CACF' },
    model: { icon: '/images/drawer/zephyr.png', name: 'GPT 3.5' },
    score: '65.1',
    lastUpdated: '2 days ago'
  },
  {
    rank: { name: '#3', color: '#EC7575' },
    model: { icon: '/images/drawer/zephyr.png', name: 'GPT 3.5' },
    score: '65.1',
    lastUpdated: '2 days ago'
  },
  {
    rank: { name: '#4', color: '#EC7575' },
    model: { icon: '/images/drawer/zephyr.png', name: 'GPT 3.5' },
    score: '65.1',
    lastUpdated: '2 days ago'
  },
  {
    rank: { name: '#5', color: '#EC7575' },
    model: { icon: '/images/drawer/zephyr.png', name: 'GPT 3.5' },
    score: '65.1',
    lastUpdated: '2 days ago'
  },
]


function LeaderboardTable() {
  const router = useRouter()
  const [order, setOrder] = useState<'-' | ''>('');
  const [orderBy, setOrderBy] = useState<string>('created_at');




  return (
    <div className='pb-[60px] pt-[1.45rem] eval-explorer-wrapper'>
      <Table<DataType>
        className="eval-explorer-table"
        columns={[
          {
            title: 'Rank',
            dataIndex: 'rank',
            key: 'rank',
            width: '25%',
            render: (text) => <div className='flex justify-start'>
              <Tags name={text.name} color={text.color} textClass="text-[#EEEEEE] text-[0.75rem]" classNames='w-[2rem] h-[1.5rem]' />
            </div>,
            sortOrder: orderBy === 'name' ? order === '-' ? 'descend' : 'ascend' : undefined,
            sorter: true,
            sortIcon: SortIcon,
          },
          {
            title: 'Model',
            dataIndex: 'model',
            key: 'model',
            width: '25%',
            render: (text) => <div className='flex justify-start items-center gap-[.2rem]'>
              {text.icon && (
                <div className='w-[0.875rem] h-[0.875rem]'>
                  <Image
                    preview={false}
                    src={text.icon}
                    style={{ width: "0.875em", height: "0.875em" }}
                    alt="Hovered Logo"
                  />
                </div>
              )}
              <Text_12_300_EEEEEE >{text.name}</Text_12_300_EEEEEE>
            </div>,
            sorter: true,
            sortIcon: SortIcon,
          },
          {
            title: 'Score',
            dataIndex: 'score',
            key: 'score',
            width: '25%',
            sorter: true,
            sortOrder: orderBy === 'text' ? order === '-' ? 'descend' : 'ascend' : undefined,
            render: (text) => <Text_12_300_EEEEEE >{text}</Text_12_300_EEEEEE>,
            sortIcon: SortIcon,
          },
          {
            title: 'Last Updated',
            dataIndex: 'lastUpdated',
            key: 'lastUpdated',
            width: '25%',
            sorter: true,
            sortOrder: orderBy === 'text' ? order === '-' ? 'descend' : 'ascend' : undefined,
            render: (text) => <Text_12_300_EEEEEE >{text}</Text_12_300_EEEEEE>,
            sortIcon: SortIcon,
          }
        ]}
        pagination={false}
        dataSource={sampleResponse}
        bordered={false}
        footer={null}
        virtual
        onRow={(record, rowIndex) => {
          return {
            onClick: async event => {
              null
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

export default LeaderboardTable;

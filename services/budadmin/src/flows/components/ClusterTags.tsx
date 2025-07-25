import React from 'react'
import { Model } from 'src/hooks/useModels'
import TagsList, { TagListeItem } from './TagsList'
import Tags from './DrawerTags'
import { successToast } from '@/components/toast'
import { LinkOutlined } from '@ant-design/icons'
import { Image, Popover } from 'antd'
import { CpuIcon } from 'lucide-react'
import { Cluster } from 'src/hooks/useCluster'
import { capitalize } from '@/lib/utils'
import { endpointStatusMapping } from '@/lib/colorMapping'

type ClusterTagsProps = {
    // cluster: Cluster
    cluster: any
    hideLink?: boolean
    hideTags?: boolean
    maxTags?: number
    hideEndPoints?: boolean
    hideType?: boolean
    hideModality?: boolean
    hideAuthor?: boolean
    available_nodes?: boolean
}

function ClusterTags(props: ClusterTagsProps) {
    const [showMore, setShowMore] = React.useState(false)
    
    if (!props.cluster) return null

    const tags: TagListeItem[] = [
        {
            color: '#D1B854',
            name: props.cluster.cpu_count ? `${props.cluster.cpu_count || 0} CPU` : '',
        },
        {
            color: '#D1B854',
            name: props.cluster.gpu_count ? `${props.cluster.gpu_count || 0} GPU` : '',
        },
        {
            color: '#D1B854',
            name: props.cluster.hpu_count ? `${props.cluster.hpu_count || 0} HPU` : '',
        },
        // {
        //     color: '#D1B854',
        //     name: `${props.cluster.total_nodes || 0} Nodes`,
        // },
        // {
        //     color: '#D1B854',
        //     name: `${props.cluster.available_nodes || 0} Available`,
        // },
        // {
            // color: '#D1B854',
            // name: `${props.cluster.total_resources || 0} of ${props.cluster.resources_used || 0}  Resourced Used`,
        // },
        // {
        //     color: '#D1B854',
        //     name: `${props.cluster.cost_per_token || 0} Cost`,
        // },
        // {
        //     color: '#D1B854',
        //     name: `${props.cluster.status || 'Status'}`,
        // },
        // {
        //     color: '#D1B854',
        //     name: `${props.cluster.created_at || 'Created At'}`,
        // },
        // {
        //     color: '#D1B854',
        //     name: `${props.cluster.modified_at || 'Modified At'}`,
        // },
        // {
        //     color: '#D1B854',
        //     name: `${props.cluster.icon || 'Icon'}`,
        // },
        // {
        //     color: '#D1B854',
        //     name: `${props.cluster.ingress_url || 'Ingress URL'}`,
        // },
    ]?.filter((item) => item.name)
    return <div className="flex flex-wrap items-center gap-[.25rem]">
        {!props.hideEndPoints && <Tags name={props.cluster.total_endpoints_count ? props.cluster.total_endpoints_count : 0} color={'#965CDE'}
            textClass="text-[.625rem]"
            image={
                (
                    <div className="bg-[#1F1F1F] w-[0.75rem] h-[0.75rem] rounded-[5px] flex justify-center items-center grow-0 shrink-0 mr-[.25rem]">
                        <Image
                            preview={false}
                            src={"/images/drawer/rocket.png"}
                            className="!w-[.75rem] !h-[.75rem]"
                            style={{ width: '.75rem', height: '.75rem' }}
                            alt="home"
                        />
                    </div>
                )
            } />}
        <TagsList data={props.maxTags > 0 ? tags.slice(0, props.maxTags) : tags} />
        {props?.cluster?.status && <Tags
            color={endpointStatusMapping[capitalize(props.cluster.status)]}
            name={capitalize(props.cluster.status)}
            textClass="text-[.625rem]"
        />}
    </div>
}

export default ClusterTags
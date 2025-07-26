import { Grid } from '@radix-ui/themes'
import { useEffect, useState } from 'react'
import GaugeChart from '../gaugeChart'
import { AppRequest } from 'src/pages/api/requests'
import Link from 'next/link';
import { useRouter } from 'next/router';

interface GaugeChartProps {
    data: {
        harmfulness: {
            title: string,
            inputValue: number,
            outputValue: number,
            color: string
        },
        hallucination: {
            title: string,
            inputValue: number,
            outputValue: number,
            color: string
        },
        sensitiveInformation: {
            title: string,
            inputValue: number,
            outputValue: number,
            color: string
        },
        promptInjection: {
            title: string,
            inputValue: number,
            outputValue: number,
            color: string
        },
    };
}

const ScoreChart: React.FC<GaugeChartProps> = ({ data }) => {
    const router = useRouter();
    const [projectId, setProjectId] = useState(null);
    const [endpointId, setEndpointId] = useState(null);
    const [scoreChartData, setScoreChartData] = useState<GaugeChartProps['data']>(data);

    useEffect(() => {
        if (router.query.projectId) {
            setProjectId(Array.isArray(router.query.projectId) ? router.query.projectId[0] : router.query.projectId);
        }
    }, [router.query.projectId]);

    useEffect(() => {
        if (router.query.endpointId) {
            setEndpointId(Array.isArray(router.query.endpointId) ? router.query.endpointId[0] : router.query.endpointId);
        }
    }, [router.query.endpointId]);

    useEffect(() => {
        if (data) {
            setScoreChartData(data);
        }
    }, [data]);

    /* Customizing the data passed to the Gauge Chart component. It just needs one value out of the input and output returned by the score service */
    const harmfulness = {
        title: scoreChartData.harmfulness.title,
        value: (scoreChartData.harmfulness.inputValue + scoreChartData.harmfulness.outputValue) / 2 * 100,
        color: scoreChartData.harmfulness.color
    }

    const hallucination = {
        title: scoreChartData.hallucination.title,
        value: (scoreChartData.hallucination.inputValue + scoreChartData.hallucination.outputValue) / 2 * 100,
        color: scoreChartData.hallucination.color
    }

    const sensitiveInformation = {
        title: scoreChartData.sensitiveInformation.title,
        value: (scoreChartData.sensitiveInformation.inputValue + scoreChartData.sensitiveInformation.outputValue) / 2 * 100,
        color: scoreChartData.sensitiveInformation.color
    }

    const promptInjection = {
        title: scoreChartData.promptInjection.title,
        value: (scoreChartData.promptInjection.inputValue + scoreChartData.promptInjection.outputValue) / 2 * 100,
        color: scoreChartData.promptInjection.color
    }

    return (
        <Grid gap="2" columns="2" rows="repeat(2,108px)" justify="between">
            <Link href={`/projects/${projectId}/endpoint/${endpointId}/harmfulness`}>
                <GaugeChart props={harmfulness} />
            </Link>
            <Link href={`/projects/${projectId}/endpoint/${endpointId}/hallucination`}>
                <GaugeChart props={hallucination} />
            </Link>
            <Link href={`/projects/${projectId}/endpoint/${endpointId}/sensitive_info`}>
                <GaugeChart props={sensitiveInformation} />
            </Link>
            <Link href={`/projects/${projectId}/endpoint/${endpointId}/prompt_injection`}>
                <GaugeChart props={promptInjection} />
            </Link>
        </Grid>
    )
}

export default ScoreChart

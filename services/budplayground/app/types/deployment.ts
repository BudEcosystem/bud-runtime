

type Provider = {
    id: string;
    name: string;
    description: string;
    type: string;
    icon: string;
};
type Tag = {
    name: string;
    color: string;
};

type Model = {
    id: string;
    name: string;
    description: string;
    uri: string;
    tags: Tag[];
    provider: Provider;
    is_present_in_model: boolean;
    strengths: string[];
    limitations: string[];
    icon: string;
};

type Project = {
    name: string;
    description: string;
    tags: Tag[];
    icon: string;
    id: string;
};

export type Endpoint = {
    id: string;
    name: string;
    status: "unhealthy" | "running";
    model: Model | string;
    project: Project | null;
    created_at: string;
};

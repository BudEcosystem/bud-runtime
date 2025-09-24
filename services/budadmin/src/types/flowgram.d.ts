declare module '@flowgram.ai/demo-fixed-layout' {
  export interface FlowNode {
    id: string;
    type: string;
    data: {
      label: string;
      description?: string;
      [key: string]: any;
    };
    position: {
      x: number;
      y: number;
    };
    style?: Record<string, any>;
  }

  export interface FlowEdge {
    id: string;
    source: string;
    target: string;
    data?: {
      label?: string;
      [key: string]: any;
    };
    style?: Record<string, any>;
  }

  export interface FlowData {
    nodes: FlowNode[];
    edges: FlowEdge[];
    groups?: any[];
  }

  export interface EditorOptions {
    data?: FlowData;
    options?: {
      layout?: any;
      minimap?: any;
      toolbar?: any;
      nodes?: any;
      edges?: any;
      background?: any;
      interaction?: any;
    };
  }

  export class FixedLayoutEditor {
    constructor(container: HTMLElement, options?: EditorOptions);
    addNode(node: FlowNode): void;
    getData(): FlowData;
    setData(data: FlowData): void;
    export(options?: { format: string }): void;
    fitView(): void;
    destroy(): void;
    on(event: string, callback: (data: any) => void): void;
  }

  export default FixedLayoutEditor;
}

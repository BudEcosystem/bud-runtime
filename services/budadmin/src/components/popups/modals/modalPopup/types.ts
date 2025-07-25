export interface TextFieldType {
  type: 'text';
  name: string;
  label: string;
  placeHolder?: string;
  search?: any;
}

export interface SelectFieldType {
  type: 'select';
  name: string;
  label: string;
  options: string[];
  placeHolder?: string;
  search?: any;
}

export type Field = TextFieldType | SelectFieldType;


export interface BudProps {
  children: React.ReactNode;
  classNames?: any 
}

export function BudDrawerLayout(props: BudProps) {
  return (
    <>
    {/* <div className={`flex-initial z-20 border-1 border-[red] form-layout mb-[2rem]`}></div> */}
    <div className={`flex-initial z-20 border-1 border-[red] form-layout !mb-[0] ${props.classNames}`}>
      {props.children}
    </div>
    </>
  );
}



import DashBoardLayout from "../layout";

export default function Chat() {
    return (
        <DashBoardLayout>
            <div style={{ width: '100%', height: '100%' }}>
                <iframe
                    src="https://inference.accubits.cloud/"
                    style={{ width: '100%', height: '100%' }}
                    frameBorder="0"
                    allowFullScreen
                />
            </div>
        </DashBoardLayout>

    )
}

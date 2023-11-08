import { createRoot } from 'react-dom/client';
console.log("react.js loaded");
function HintButton() {
    return(
            <div>
                <a role="button" class="weui-btn weui-btn_default" >tip</a>
            </div>
        );
}

const domNode = document.getElementById('hint');
const root = createRoot(domNode);
root.render(<HintButton />);
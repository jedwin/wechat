//import { createRoot } from 'react-dom/client';
let timeout = 500;
const showHint = () => {
    // show the confirm window, if user click the confirm button, then show the hint string
    
    weui.confirm('<h1>确定吗？</h1>', 
            function () {
                setTimeout(function () {
                    weui.alert('好的');
                }, timeout);
            }, function () {
                setTimeout(function() {
                    weui.alert('不好');
                }, timeout);
            }
    );
}

const HintButton = () => {
    return(
            <div>
                <a role="button" className="weui-btn weui-btn_default" onClick={showHint} >tip</a>
            </div>
        );
}
// create a function to show the hint string in popup window

ReactDOM.render(
    <HintButton />,
    document.querySelector('#hint')
);
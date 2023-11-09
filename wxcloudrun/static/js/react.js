// import { createRoot } from 'react-dom/client';

function CommonDialog({title, content}) {
    
    return(
        <div>
            <a role="button" className="weui-btn weui-btn_default" onClick={()=>{weui.alert({content});}}>{title}</a>
        </div>
    );
}

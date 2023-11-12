// import { createRoot } from 'react-dom/client';

function CommonDialog({title, content}) {
    
    return(
        <div>
            <a role="button" className="weui-btn weui-btn_default" onClick={()=>{weui.alert(`${content}`);}}>{title}</a>
        </div>
    );
}

function ConfirmLinkDialog({title, content, to_link, style="weui-btn weui-btn_default"}) {
    const confirm = () => {
    
        weui.confirm(`${content}`, 
            function () {
                globalThis.location=to_link;
            }
    )};

    return(
        <div>
            <a role="button" className={style} onClick={confirm}>{title}</a>
        </div>
    );
}
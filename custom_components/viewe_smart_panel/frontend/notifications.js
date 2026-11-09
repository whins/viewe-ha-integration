// Use HA's global notification manager so feedback never changes the panel layout.
export function closeToast(host,id="viewe-editor-action") {
  host.dispatchEvent(new CustomEvent("hass-notification",{detail:{id,duration:0},bubbles:true,composed:true}));
}
export function closeErrorDetails(host) {
  const dialog=host._vieweErrorDialog;
  if(!dialog)return;
  host._vieweErrorDialog=null;
  if(dialog.open)dialog.close();
  dialog.remove();
}
export function openErrorDetails(host,message,{title,closeLabel}) {
  closeErrorDetails(host);
  const dialog=document.createElement("dialog");dialog.className="viewe-error-details";
  dialog.setAttribute("aria-label",title);
  const style=document.createElement("style");
  style.textContent=`dialog.viewe-error-details{box-sizing:border-box;width:min(640px,calc(100vw - 32px));max-height:80vh;border:1px solid var(--divider-color,#666);border-radius:16px;padding:24px;color:var(--primary-text-color,#222);background:var(--card-background-color,#fff);font-family:var(--primary-font-family,system-ui)}dialog.viewe-error-details::backdrop{background:rgba(0,0,0,.5)}dialog.viewe-error-details h2{font-size:20px;margin:0 0 18px}dialog.viewe-error-details pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere;max-height:55vh;overflow:auto}dialog.viewe-error-details button{display:block;margin-left:auto;padding:10px 18px;border:0;border-radius:8px;background:var(--primary-color,#087e8b);color:var(--text-primary-color,#fff);font:inherit;cursor:pointer}`;
  const heading=document.createElement("h2");heading.textContent=title;
  const content=document.createElement("pre");content.textContent=message;
  const close=document.createElement("button");close.textContent=closeLabel;close.autofocus=true;
  close.addEventListener("click",()=>dialog.close());
  dialog.addEventListener("close",()=>{dialog.remove();if(host._vieweErrorDialog===dialog)host._vieweErrorDialog=null;});
  dialog.append(style,heading,content,close);document.body.append(dialog);host._vieweErrorDialog=dialog;
  dialog.showModal();
}
export function showToast(host,message,{error=false,id="viewe-editor-action",detailsLabel="Details",title="Action failed",closeLabel="Close"}={}) {
  const full=String(message);
  const detail={id,message:full.length>180?full.slice(0,177)+"…":full,duration:error?-1:4000,dismissable:true};
  if(error)detail.action={text:detailsLabel,action:()=>openErrorDetails(host,full,{title,closeLabel})};
  host.dispatchEvent(new CustomEvent("hass-notification",{detail,bubbles:true,composed:true}));
}

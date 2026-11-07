// Bind only applied, visible, non-demo widgets to their original HA entities.
export function profileEntities(profile) {
  const entries=new Map();
  const add=(entity_id,label="")=>{
    if(typeof entity_id!=="string" || !/^(light|switch|climate|weather|sensor|binary_sensor|script|automation)\.[a-z0-9_]+$/.test(entity_id))return;
    if(!entries.has(entity_id))entries.set(entity_id,{key:entity_id,entity_id,label,kind:"entity",info_entity_id:entity_id});
  };
  for(const widget of profile?.pages || []) {
    if(!widget.visible || widget.demo)continue;
    if(widget.template==="bc250") {
      // Never expose a raw Power button: it can shut down an already running PC.
      const key="bc250:"+widget.id;
      entries.set(key,{key,kind:"bc250",entity_id:widget.power_entity_id,label:widget.name,
        info_entity_id:widget.entity_id,running_entity_id:widget.entity_id,
        guard_script:widget.guard_script || "script.viewe_guarded_start"});
    } else if(widget.template==="actions") {
      for(const action of widget.actions || [])add(action.entity_id,action.name);
    } else if(widget.template==="temperature_humidity") {
      add(widget.temperature_entity_id,widget.name);add(widget.humidity_entity_id,widget.name);
    } else if(widget.template!=="clock")add(widget.entity_id,widget.name);
  }
  return [...entries.values()];
}

export function entityReady(state, allowUnknown=false) {
  return !!state && !!state.state && state.state!=="unavailable" && (allowUnknown || state.state!=="unknown");
}

export function controlAction(entry, states) {
  if(entry.kind==="bc250") {
    if(states[entry.running_entity_id]?.state!=="off" || !entityReady(states[entry.entity_id],true) || !entityReady(states[entry.guard_script]))return null;
    return {domain:"script",service:"turn_on",data:{entity_id:entry.guard_script,
      variables:{state_entity_id:entry.running_entity_id,control_entity_id:entry.entity_id}},label:"startControl"};
  }
  if(!entityReady(states[entry.entity_id]))return null;
  const domain=entry.entity_id.split(".")[0];
  if(domain==="light" || domain==="switch")return {domain,service:"toggle",data:{entity_id:entry.entity_id},label:"toggleControl"};
  if(domain==="script")return {domain,service:"turn_on",data:{entity_id:entry.entity_id},label:"runControl"};
  if(domain==="automation")return {domain,service:"trigger",data:{entity_id:entry.entity_id,skip_condition:false},label:"runControl"};
  return null;
}

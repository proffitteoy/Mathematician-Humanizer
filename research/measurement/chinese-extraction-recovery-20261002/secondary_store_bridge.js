/* Runs inside functions.exec with tools/store/load supplied. Never prints payloads.
   The store is agent-local, secondary only, and has no durability guarantee. */
return async function secondaryStoreBridge(options) {
  const { prefix, generation, indexFile, helperFile, readbackDirectory, readbackArchive, syntheticOnly = false } = options;
  const q = s => "'" + String(s).replace(/'/g, "'\\''") + "'";
  const command = async (cmd, max = 4000) => {
    const r = await tools.exec_command({cmd, max_output_tokens:max, yield_time_ms:1000});
    if (r.session_id) throw new Error('Unexpected asynchronous small-chunk command');
    if (r.exit_code !== 0) throw new Error('Secondary-cache command failed; payload suppressed');
    return r.output;
  };
  const index = JSON.parse(await command('cat '+q(indexFile), 100000));
  if (index.archive_bytes > 32*1024*1024) throw new Error('Archive exceeds32MiB cap');
  const old = load(prefix+':active');
  const candidate = prefix+':generation:'+generation;
  const chunkKeys = index.chunks.map((_,i)=>candidate+':chunk:'+i);
  store(candidate+':index',index);
  store(candidate+':state',{verified:false,committed_cache_count:index.committed_cache_count,archive_sha256:index.archive_sha256,syntheticOnly});
  let cursor=0;
  async function worker(){
    while(cursor<index.chunks.length){
      const i=cursor++;
      const b64=await command('python '+q(helperFile)+' read-chunk --index '+q(indexFile)+' --number '+i, 100000);
      if (b64.length!==4*Math.ceil(index.chunks[i].bytes/3) || !/^[A-Za-z0-9+/]*={0,2}$/.test(b64)) throw new Error('Truncated or invalid base64 chunk; no promotion');
      store(chunkKeys[i],b64);
      const readback=load(chunkKeys[i]);
      if(readback!==b64)throw new Error('Tool-store immediate readback mismatch');
      const write=JSON.parse(await command('python '+q(helperFile)+' write-chunk --directory '+q(readbackDirectory)+' --number '+i+' --base64 '+q(readback)));
      if(write.bytes!==index.chunks[i].bytes || write.sha256!==index.chunks[i].sha256)throw new Error('Stored chunk SHA mismatch');
    }
  }
  await Promise.all(Array.from({length:4},()=>worker()));
  // The archive-level readback verifies every stored byte, archive structure,
  // committed count and every original JSON payload hash before promotion.
  const r=await tools.exec_command({cmd:'python '+q(helperFile)+' finish-readback --directory '+q(readbackDirectory)+' --index '+q(indexFile)+' --destination '+q(readbackArchive),max_output_tokens:4000,yield_time_ms:1000});
  let final=r;
  if(r.session_id){
    do {final=await tools.write_stdin({session_id:r.session_id,chars:'',yield_time_ms:1000,max_output_tokens:4000});} while(final.session_id);
  }
  if(final.exit_code!==0)throw new Error('Archive readback verification failed; previous generation retained');
  const verified=JSON.parse(final.output);
  if(!verified.verified || !verified.tool_store_archive_readback_verified || verified.archive_sha256!==index.archive_sha256 || verified.committed_cache_count!==index.committed_cache_count)throw new Error('Incomplete archive verification; no promotion');
  const active={version:'zh-secondary-tool-store/1.0.0',generation,archive_sha256:index.archive_sha256,archive_bytes:index.archive_bytes,committed_cache_count:index.committed_cache_count,index,chunkKeys,syntheticOnly,verified:true,durability:'secondary_only_no_guarantee',store_scope:'this_agent_only'};
  store(candidate+':state',active);
  store(prefix+':active',active);
  // Old payloads are released only after the new complete generation is verified.
  if(old && old.generation!==generation){
    store(prefix+':previous_receipt',{generation:old.generation,archive_sha256:old.archive_sha256,committed_cache_count:old.committed_cache_count,replaced_only_after_verified_success:true});
    for(const key of old.chunkKeys||[])store(key,null);
    store(prefix+':generation:'+old.generation+':index',null);
    store(prefix+':generation:'+old.generation+':state',null);
  }
  return {verified:true,generation,archive_sha256:active.archive_sha256,compressed_bytes:active.archive_bytes,last_backed_up_count:active.committed_cache_count,chunk_count:chunkKeys.length,synthetic_only:syntheticOnly,durability:active.durability,store_scope:active.store_scope,active_key:prefix+':active'};
};

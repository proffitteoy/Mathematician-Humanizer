/* Restore an agent-local secondary generation without its original filesystem.
   Requires this public helper source to be restored; no raw corpus access. */
return async function restoreSecondaryStore(options){
 const {prefix,helperFile,workDirectory,restoreDirectory}=options;
 const q=s=>"'"+String(s).replace(/'/g,"'\\''")+"'";
 const active=load(prefix+':active');
 if(!active||!active.verified)throw new Error('No verified secondary generation available');
 const indexFile=workDirectory+'/chunk_index.json';
 const r=await tools.exec_command({cmd:'mkdir -p '+q(workDirectory)+' && python -c '+q('from pathlib import Path; import sys; Path(sys.argv[1]).write_text(sys.argv[2])')+' '+q(indexFile)+' '+q(JSON.stringify(active.index)),max_output_tokens:1000,yield_time_ms:1000});
 if(r.exit_code!==0)throw new Error('Cannot materialize secondary index');
 let cursor=0;
 async function worker(){while(cursor<active.chunkKeys.length){
  const i=cursor++;const b64=load(active.chunkKeys[i]);
  if(typeof b64!=='string'||b64.length!==4*Math.ceil(active.index.chunks[i].bytes/3))throw new Error('Missing secondary chunk');
  const result=await tools.exec_command({cmd:'python '+q(helperFile)+' write-chunk --directory '+q(workDirectory+'/chunks')+' --number '+i+' --base64 '+q(b64),max_output_tokens:1000,yield_time_ms:1000});
  if(result.exit_code!==0)throw new Error('Secondary chunk restore failed');
  const out=JSON.parse(result.output);if(out.sha256!==active.index.chunks[i].sha256)throw new Error('Stored chunk corruption');
 }}
 await Promise.all(Array.from({length:4},()=>worker()));
 async function finish(cmd){
  let r=await tools.exec_command({cmd,max_output_tokens:4000,yield_time_ms:1000});
  if(r.session_id){const id=r.session_id;do{r=await tools.write_stdin({session_id:id,chars:'',yield_time_ms:1000,max_output_tokens:4000});}while(r.session_id);}
  if(r.exit_code!==0)throw new Error('Secondary archive validation/restoration failed');return JSON.parse(r.output);
 }
 const archive=workDirectory+'/restored_secondary.tar.xz';
 const check=await finish('python '+q(helperFile)+' finish-readback --directory '+q(workDirectory+'/chunks')+' --index '+q(indexFile)+' --destination '+q(archive));
 if(check.archive_sha256!==active.archive_sha256||check.committed_cache_count!==active.committed_cache_count)throw new Error('Secondary archive identity mismatch');
 const recovered=await finish('python '+q(helperFile)+' restore --archive '+q(archive)+' --destination '+q(restoreDirectory));
 return {restored:true,from_generation:active.generation,synthetic_only:active.syntheticOnly,committed_cache_count:recovered.committed_cache_count,archive_sha256:recovered.archive_sha256,exact_original_json_bytes_verified:recovered.exact_original_json_bytes_verified,gzip_container_hashes_preserved:recovered.gzip_container_hashes_preserved,gzip_container_hashes_regenerated:recovered.gzip_container_hashes_regenerated,durability:'secondary_only_no_guarantee'};
};

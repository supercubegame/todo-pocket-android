"""Observe the existing API34 preview build. No new Gradle arguments, retry or deadline.

Gradle writes directly to the artifact file, so runner cancellation cannot discard already
emitted output. The complete original child output, not heartbeat/header text, is supplied
to the unchanged 429 classifier. An unfinished log is never a successful build receipt.
"""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

COMMAND = ('gradle','--no-daemon','--console=plain','assembleDebug','assembleDebugAndroidTest','lintDebug')

def current_build_observer(command, path, env):
    if (tuple(command)!=COMMAND or Path(path)!=Path('build.log') or
        any(env.get(k)!=v for k,v in {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'supercubegame/todo-pocket-android','GITHUB_JOB':'database','TEST_API':'34','OBSERVE_CURRENT_API34':'1','BUILD_LINT':'true','BUILD_429_EXECUTE':'true','BUILD_LOG':'build.log'}.items()) or
        env.get('BUILD_ROLE') or not re.fullmatch(r'[a-f0-9]{40}',env.get('GITHUB_SHA','')) or
        not re.fullmatch(r'[1-9][0-9]{0,19}',env.get('GITHUB_RUN_ID','')) or not re.fullmatch(r'[1-9][0-9]{0,3}',env.get('GITHUB_RUN_ATTEMPT',''))):
        raise ValueError('not the current signed API34 database build')
    identity=None;last_size=0;last_number=0
    origin={k:env[k] for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT')}
    def invoke(actual,number):
        nonlocal identity,last_size,last_number
        if tuple(actual)!=COMMAND or type(number) is not int or number!=last_number+1 or not 1<=number<=3:raise ValueError('unexpected build invocation')
        fd=os.open(path,os.O_RDWR|os.O_APPEND|os.O_NOFOLLOW|(os.O_CREAT|os.O_EXCL if number==1 else 0),0o600)
        with os.fdopen(fd,'a+b',buffering=0) as f:
            st=os.fstat(fd);key=(st.st_dev,st.st_ino)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size!=last_size or (number!=1 and identity!=key):raise ValueError('previous attempt log not owned')
            identity=key;last_number=number
            mark=dict(origin,attempt=number,api=34,scope='BUILD_STARTED_NOT_COMPLETION');header=('\nBUILD_ATTEMPT '+str(number)+'\nAPI34_BUILD_START '+json.dumps(mark)+'\n').encode();f.write(header);sys.stdout.buffer.write(header);sys.stdout.buffer.flush();start=os.fstat(fd).st_size
            # Keep the original job timeout and process ownership. No extra shell or process killer.
            with subprocess.Popen(list(actual),stdout=f,stderr=subprocess.STDOUT) as proc:
                pos=start
                def forward(stop):
                    nonlocal pos
                    while pos<stop:
                        block=os.pread(fd,min(65536,stop-pos),pos)
                        if not block:raise OSError('incomplete live build log')
                        sys.stdout.buffer.write(block);pos+=len(block)
                    sys.stdout.buffer.flush()
                while True:
                    try:code=proc.wait(timeout=0.75)
                    except subprocess.TimeoutExpired:
                        forward(os.fstat(fd).st_size);continue  # observation only, never retries the build
                    stop=os.fstat(fd).st_size;forward(stop);break
            # pread uses an independent offset: a later retry cannot receive output from an earlier one.
            raw=os.pread(fd,stop-start,start) if stop>start else b''
            if len(raw)!=stop-start:raise OSError('incomplete final build log')
            footer=('\nAPI34_BUILD_END '+json.dumps(dict(mark,scope='BUILD_PROCESS_EXIT_NOT_DEVICE_RESULT',returncode=code,output_bytes=len(raw)))+'\n').encode();f.write(footer);sys.stdout.buffer.write(footer);sys.stdout.buffer.flush();last_size=os.fstat(fd).st_size
            return code,raw.decode('utf-8',errors='replace')
    return invoke

def scope_controls():
    # Do not launch Gradle from a self-test. Prove the shared YAML anchor cannot select
    # this path for an export, old package, other job/API or arbitrary log/command.
    e={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'supercubegame/todo-pocket-android','GITHUB_JOB':'database','TEST_API':'34','OBSERVE_CURRENT_API34':'1','BUILD_LINT':'true','BUILD_429_EXECUTE':'true','BUILD_LOG':'build.log','GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'12','GITHUB_RUN_ATTEMPT':'1'}
    actual=current_build_observer(COMMAND,'build.log',e);refused=0
    for k,v in [('TEST_API','26'),('OBSERVE_CURRENT_API34',''),('GITHUB_ACTIONS','false'),('GITHUB_JOB','export_probe'),('BUILD_ROLE','PINNED_OLD_SINGLETON'),('GITHUB_REPOSITORY','other'),('BUILD_LOG','export-probe-build.log'),('BUILD_LINT','false'),('GITHUB_SHA','unbound'),('GITHUB_RUN_ID',''),('GITHUB_RUN_ATTEMPT','0')]:
        try:current_build_observer(COMMAND,'build.log',dict(e,**{k:v}))
        except ValueError:refused+=1
        else:raise AssertionError('unscoped build was accepted')
    for cmd,path in [(COMMAND[:-1],'build.log'),(COMMAND,'other.log')]:
        try:current_build_observer(cmd,path,e)
        except ValueError:refused+=1
        else:raise AssertionError('unscoped command/log was accepted')
    for cmd,n in [(COMMAND,2),(COMMAND,0),(COMMAND[:-1],1)]:
        try:actual(cmd,n)
        except ValueError:refused+=1
        else:raise AssertionError('out-of-order build attempt was accepted')
    assert refused==16;print('API34_CURRENT_LOG_SCOPE 1 valid and 16 refusals, no child build invoked',flush=True)

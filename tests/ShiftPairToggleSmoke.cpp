// Paired punctuation keys typed with Shift ( ( " < { ) are consumed by the
// client and never reach Rime. Without a follow-up event, Rime's
// ascii_composer sees Shift down + Shift up alone and toggles 中文/英文.
// The client now sends the intercepted key's release; verify on the real engine.
#include "rime_api.h"
#include <dlfcn.h>
#include <iostream>
#include <string>
static const int kShift_L=0xffe1,kShift=1<<0,kRelease=1<<30;
int main(int argc,char** argv){
 if(argc<3)return 2;
 auto library=dlopen(argv[1],RTLD_NOW|RTLD_GLOBAL);if(!library)return 3;
 auto api=((RimeApi*(*)())dlsym(library,"rime_get_api"))();
 RIME_STRUCT(RimeTraits,t);t.shared_data_dir=argv[2];t.user_data_dir=argv[2];t.log_dir=argv[2];t.app_name="rime.kongime.shift-pair-test";t.min_log_level=3;
 api->setup(&t);api->initialize(&t);auto session=api->create_session();
 if(!api->select_schema(session,argc>3?argv[3]:"qingyan"))return 4;
 int failures=0;
 auto committed=[&]{RIME_STRUCT(RimeCommit,c);bool any=api->get_commit(session,&c);if(any)api->free_commit(&c);
  RIME_STRUCT(RimeContext,x);api->get_context(session,&x);bool composing=x.composition.length>0;api->free_context(&x);return any||composing;};
 auto check=[&](const char* name,bool ok){std::cout<<(ok?"PASS ":"FAIL ")<<name<<std::endl;if(!ok)++failures;};
 auto tap=[&](int key){api->process_key(session,kShift_L,0);if(key)api->process_key(session,key,kShift|kRelease);api->process_key(session,kShift_L,kShift|kRelease);};
 for(bool ascii:{false,true}){
  for(int key:{'(','"','<','{'}){
   api->clear_composition(session);api->set_option(session,"ascii_mode",ascii);
   tap(key);
   std::string label=std::string(ascii?"英文":"中文")+" Shift+"+char(key);
   check((label+" 保持输入状态").c_str(),api->get_option(session,"ascii_mode")==ascii);
   check((label+" 不产生文字").c_str(),!committed());
  }
 }
 api->clear_composition(session);api->set_option(session,"ascii_mode",false);tap(0);
 check("单按 Shift 仍可切换中英文",api->get_option(session,"ascii_mode"));
 api->destroy_session(session);api->finalize();return failures?1:0;
}

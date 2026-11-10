// 用真实的 Rime 引擎读出候选：每个输入打印一行「输入<TAB>候选1|注释1<TAB>候选2|注释2…」（最多 5 个）。
// 用法：everyday-smoke <librime 路径> <已生成配置的目录> 输入…
#include "rime_api.h"
#include <dlfcn.h>
#include <iostream>
#include <string>
int main(int argc,char**argv){
 if(argc<4)return 2;
 auto lib=dlopen(argv[1],RTLD_NOW|RTLD_GLOBAL);if(!lib){std::cerr<<dlerror();return 3;}
 auto entry=(RimeApi*(*)())dlsym(lib,"rime_get_api");if(!entry)return 3;
 auto api=entry();
 RIME_STRUCT(RimeTraits,t);t.shared_data_dir=argv[2];t.user_data_dir=argv[2];t.log_dir=argv[2];t.app_name="rime.kongflow.everyday";t.min_log_level=2;
 api->setup(&t);api->initialize(&t);api->start_maintenance(true);api->join_maintenance_thread();
 auto session=api->create_session();
 if(!api->select_schema(session,"qingyan")){std::cerr<<"schema failed";return 4;}
 api->set_option(session,"ascii_mode",false);
 for(int i=3;i<argc;i++){
  api->clear_composition(session);api->simulate_key_sequence(session,argv[i]);
  std::cout<<argv[i];
  RimeCandidateListIterator it{};int count=0;
  if(api->candidate_list_begin(session,&it)){
   while(count<5&&api->candidate_list_next(&it)){count++;std::cout<<"\t"<<it.candidate.text<<"|"<<(it.candidate.comment?it.candidate.comment:"");}
   api->candidate_list_end(&it);
  }
  std::cout<<std::endl;
 }
 api->destroy_session(session);api->finalize();
}

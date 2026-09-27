#include "rime_api.h"
#include <dlfcn.h>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
int main(int argc, char** argv) {
 if(argc!=4)return 2;
 auto library=dlopen(argv[1],RTLD_NOW|RTLD_GLOBAL);if(!library)return 3;
 auto api=((RimeApi*(*)())dlsym(library,"rime_get_api"))();
 RIME_STRUCT(RimeTraits,t);t.shared_data_dir=argv[2];t.user_data_dir=argv[2];t.log_dir=argv[2];t.app_name="rime.kongime.pause-test";t.min_log_level=3;
 api->setup(&t);api->initialize(&t);auto session=api->create_session();if(!api->select_schema(session,"qingyan"))return 4;
 api->set_option(session,"ascii_mode",false);
 auto candidates=[&](const char* code) {
  api->clear_composition(session);api->simulate_key_sequence(session,code);
  std::vector<std::string> rows;RimeCandidateListIterator it{};
  if(api->candidate_list_begin(session,&it)){while(rows.size()<30&&api->candidate_list_next(&it))rows.push_back(std::string(it.candidate.text)+"\t"+(it.candidate.comment?it.candidate.comment:""));api->candidate_list_end(&it);}return rows;
 };
 auto choose=[&](const char* code,const char* word) {
  candidates(code);int found=-1,index=0;RimeCandidateListIterator it{};
  if(api->candidate_list_begin(session,&it)){while(index<1000&&api->candidate_list_next(&it)){if(std::string(it.candidate.text)==word){found=index;break;}++index;}api->candidate_list_end(&it);}
  if(found<0 || !api->select_candidate(session,found))throw std::runtime_error("cannot select test candidate");
  RIME_STRUCT(RimeCommit,commit);if(!api->get_commit(session,&commit)) {api->commit_composition(session);if(!api->get_commit(session,&commit))throw std::runtime_error("missing commit");}
  if(std::string(commit.text)!=word)throw std::runtime_error("wrong committed text");api->free_commit(&commit);
  api->process_key(session,' ',0); // finish the transaction
 };
 std::string mode=argv[3];bool paused=mode=="pause";
 if(paused){
  for(auto code:{"nihao","nh","ni'h"}){
   api->set_option(session,"kongime_pause_learning",false);auto before=candidates(code);
   api->clear_composition(session);api->set_option(session,"kongime_pause_learning",true);auto after=candidates(code);
   if(before.empty() || before!=after)throw std::runtime_error("pause changed ranking or comments");
  }
 }
 api->clear_composition(session);api->set_option(session,"kongime_pause_learning",paused);
 for(int i=0;i<5;i++){choose("nihao","你好");if(paused){choose("zhongguo","中国");choose("nh","你好");choose("ni'h","你好");choose("nihaozhongguo","你好中国");}}
 if(mode=="resume") {api->set_option(session,"kongime_pause_learning",true);choose("nh","你好");api->set_option(session,"kongime_pause_learning",false);choose("nh","你好");}
 api->destroy_session(session);api->finalize();std::cout<<"PASS "<<mode<<std::endl;
}

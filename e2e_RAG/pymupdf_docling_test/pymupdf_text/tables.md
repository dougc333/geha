# pymupdf_text: 15 tables from 1706.03762v7.pdf

## Table 1 (page 1, 48x9)
|Col1|repr|oduce the ta|bles and|figures in this|paper solely|for use in|journalis|tic or|
|---|---|---|---|---|---|---|---|---|
|||||scholarly|works.||||
|||||<br>|<br>||||
||||**Atte**|**ntion Is**|**  All You**|**    Need**|||
||||||||||
|23|||||||||
|0|**As**|**hish Vaswani**|_∗_<br>|**Noam Shazeer**_∗_|**Niki Pa**|** rmar**_∗_|**Jakob U**|** szkoreit**_∗_|
|2|G|oogle Brain||Google Brain|Google R|esearch|Google R|esearch|
|g|`avasw`|`ani@google.`|`com`<br>`no`|`am@google.com`|`nikip@goo`|`gle.com`|`usz@goog`|`le.com`|
|u|||||||||
|A||**Llion Jones**_∗_||**Aidan N. Gom**|**  ez**_∗†_|**Łuka**|**sz Kaiser**_∗_||
|2|G|oogle Research||University of To|ronto|Goo|gle Brain||
||`lli`|`on@google.c`|`om`<br>`a`|`idan@cs.toron`|`to.edu`<br>`l`|`ukaszkais`|`er@googl`|`e.com`|
|L]|||||||||
|C||||**Illia Polos**|** ukhin**_∗‡_||||
|.|||`i`|`llia.polosukh`|`in@gmail.co`|`m`|||
|[cs|||||||||
||||||||||
||||||||||
|7||||**Abst**|**ract**||||
|v|||||||||
|2||The dominant|sequence|transduction mo|dels are based|on complex|recurrent|or|
|76||convolutional|neural net|works that inclu|de an encoder|and a decod|er. The be|st|
|3||performing m|odels also|connect the enc|oder and deco|der through|an attentio|n|
|0||mechanism.|We propos|e a new simple|network archit|ecture, the|Transform|er,|
|.||based solely on|attention|mechanisms, disp|ensing with rec|urrence and|convolutio|ns|
|6||entirely. Exp|eriments o|n two machine|translation task|s show the|se models|to|
|70||be superior in|quality w|hile being more p|arallelizable a|nd requiring|significant|ly|
|1||less time to tr|ain. Our|model achieves 2|8.4 BLEU on|the WMT 2|014 Englis|h-|
|:||to-German tra|nslation t|ask, improving o|ver the existin|g best resul|ts, includin|g|
|v||ensembles, by|over 2 BL|EU. On the WMT|2014 English-|to-French tra|nslation tas|k,|
|Xi||our model esta|blishes a n|ew single-model|state-of-the-art|BLEU score|of 41.8 aft|er|
|r||training for 3.|5 days on|eight GPUs, a s|mall fraction of|the training|costs of th|e|
|a||best models fr|om the lite|rature. We show|that the Transf|ormer gener|alizes well|to|
|||other tasks by|applying|it successfully to|English consti|tuency parsi|ng both wi|th|
|||large and limit|ed trainin|g data.|||||
|||<br>|<br>|<br>|||||
||_∗_Equa|l contribution. Li|sting order|is random. Jakob p|roposed replacin|g RNNs with|self-attention|and started|
||the effort|to evaluate this i|dea. Ashis|h, with Illia, design|ed and impleme|nted the first|Transformer|models and|
||has been c|rucially involved|in every as|pect of this work.|Noam proposed s|caled dot-prod|uct attention|, multi-head|
||attention|and the paramet|er-free posi|tion representation|and became the|other person|involved in|nearly every|
||detail. Ni|ki designed, imp|lemented, t|uned and evaluated|countless mode|l variants in o|ur original c|odebase and|
||tensor2ten|sor. Llion also e|xperimente|d with novel mode|l variants, was re|sponsible for|our initial co|debase, and|
||efficient in|ference and visu|alizations.|Lukasz and Aidan s|pent countless lo|ng days desig|ning various|parts of and|
||implemen|ting tensor2tenso|r, replacing|our earlier codeba|se, greatly impro|ving results an|d massively|accelerating|
||our resear<br>|ch.<br>|||||||
||_†_Work<br>|performed whil<br>|e at Google<br>|Brain.<br>|||||
||_‡_Work|performed whil|e at Google|Research.|||||



## Table 2 (page 2, 64x5)
|1 Introduction|Col2|Col3|Col4|Col5|
|---|---|---|---|---|
||||||
|Recurrent neural netw|orks, long sho|rt-term memory [1|3] and gated recurrent [7]|neural networks|
|in particular, have bee|n firmly establ|ished as state of th|e art approaches in sequen|ce modeling and|
|transduction problems|such as langu|age modeling and|machine translation [35, 2|, 5]. Numerous|
|efforts have since conti|nued to push th|e boundaries of recu|rrent language models and|encoder-decoder|
|architectures [38, 24,|15].||||
|<br>|<br>||||
|Recurrent models typi|cally factor co|mputation along th|e symbol positions of the i|nput and output|
|sequences. Aligning t|he positions to|steps in computatio|n time, they generate a seq|uence of hidden|
||||||
|states_ ht_, as a function|of the previou|s hidden state_ ht−_1|and the input for position_ t_|. This inherently|
|sequential nature precl|udes paralleliza|<br>   tion within training|<br>      examples, which becomes|critical at longer|
|sequence lengths, as m|emory constra|ints limit batching a|cross examples. Recent w|ork has achieved|
|significant improveme|nts in computat|ional efficiency thro|ugh factorization tricks [21|] and conditional|
|computation [32], whi|le also improv|ing model perform|ance in case of the latter. T|he fundamental|
|constraint of sequentia|l computation,|however, remains.|||
|<br>|<br>|<br>|||
|Attention mechanisms|have become a|n integral part of c|ompelling sequence modeli|ng and transduc-|
|tion models in various|tasks, allowin|g modeling of depe|ndencies without regard to|their distance in|
|the input or output seq|uences [2, 19].|In all but a few case|s [27], however, such atten|tion mechanisms|
|are used in conjunctio|n with a recurr|ent network.|||
|<br>|<br>|<br>|||
|In this work we propo|se the Transfo|rmer, a model arch|itecture eschewing recurre|nce and instead|
|relying entirely on an|attention mech|anism to draw glob|al dependencies between i|nput and output.|
|The Transformer allow|s for significa|ntly more paralleliz|ation and can reach a new s|tate of the art in|
|translation quality afte|r being trained|for as little as twel|ve hours on eight P100 GP|Us.|
|<br><br>|||||
|**2**<br>**Background**|||||
||||||
|The goal of reducing s|equential comp|utation also forms t|he foundation of the Exten|ded Neural GPU|
|[16], ByteNet [18] and|ConvS2S [9],|all of which use con|volutional neural networks|as basic building|
|block, computing hidd|en representatio|ns in parallel for all|input and output positions.|In these models,|
|the number of operatio|ns required to r|elate signals from t|wo arbitrary input or output|positions grows|
|in the distance betwee|n positions, line|arly for ConvS2S a|nd logarithmically for Byte|Net. This makes|
|it more difficult to lea|rn dependenci|es between distant|positions [12]. In the Tra|nsformer this is|
|reduced to a constant|number of op|erations, albeit at th|e cost of reduced effectiv|e resolution due|
|to averaging attention|-weighted pos|itions, an effect we|counteract with Multi-He|ad Attention as|
|described in section 3.|2.||||
|<br>|<br>||||
|Self-attention, sometim|es called intra|-attention is an atten|tion mechanism relating di|fferent positions|
|of a single sequence i|n order to com|pute a representatio|n of the sequence. Self-at|tention has been|
|used successfully in a|variety of task|s including reading|comprehension, abstractive|summarization,|
|textual entailment and|learning task-i|ndependent sentenc|e representations [4, 27, 2|8, 22].|
|<br>|<br>|<br>|<br>|<br>|
|End-to-end memory n|etworks are b|ased on a recurrent|attention mechanism inste|ad of sequence-|
|aligned recurrence and|have been sho|wn to perform well|on simple-language questio|n answering and|
|language modeling tas|ks [34].||||
|<br>|<br>||||
|To the best of our kn|owledge, how|ever, the Transform|er is the first transductio|n model relying|
|entirely on self-attenti|on to compute|representations of i|ts input and output without|using sequence-|
|aligned RNNs or conv|olution. In the|following sections,|we will describe the Trans|former, motivate|
|self-attention and disc|uss its advanta|ges over models suc|h as [17, 18] and [9].||
|<br><br>|<br>||||
|**3**<br>**Model Archit**|** ecture**||||
|<br>|<br>||||
|Most competitive neur|al sequence tra|nsduction models h|ave an encoder-decoder str|ucture [5, 2, 35].|
||||||
|Here, the encoder ma|ps an input se|quence of symbol|representations (_x_1_, ..., xn_|) to a sequence|
||||||
|of continuous represe|ntations **z** =|(_z_1_, ..., zn_). Give|**z**, the decoder then gen|rates an output|
||||||
|sequence (_y_1_, ..., ym_)|of symbols on|e element at a time|At each step the model is|auto-regressive|
|[10], consuming the p|reviously gener|ated symbols as ad|ditional input when genera|ting the next.|



## Table 3 (page 3, 29x8)
|Col1|Col2|Figure 1: The|Transformer -|model|architectu|re.|Col8|
|---|---|---|---|---|---|---|---|
|||<br>|<br>|<br>|<br>|<br>||
|The Transform|er follows|this overall ar|chitecture usin|g stack|ed self-at|tention and poi|nt-wise, fully|
|connected laye|rs for bot|h the encoder a|nd decoder, sh|own i|n the left|and right halve|s of Figure 1,|
|respectively.||||||||
|||||||||
|**3.1**<br>**Encoder**|** and Deco**|**  der Stacks**||||||
|<br>|<br>|<br>||||||
|**Encoder:**<br>Th|e encoder|is composed|of a stack of|_N_ = 6|identical|layers. Each l|ayer has two|
|sub-layers. The|first is a|multi-head self|-attention mec|hanism|, and the|second is a sim|ple, position-|
|wise fully conn|ected fee|d-forward netw|ork. We empl|oy a re|sidual con|nection [11] ar|ound each of|
|the two sub-la|yers, follo|wed by layer|normalization|[1]. T|hat is, the|output of eac|h sub-layer is|
|LayerNorm(_x_|+ Sublay|er(_x_)), where|Sublayer(_x_) i|s the f|unction im|plemented by|the sub-layer|
|itself. To facilit|ate these r|esidual connec|tions, all sub-l|ayers i|n the mod|el, as well as th|e embedding|
|||||||||
|layers, produce|outputs o|f dimension_ d_m|odel = 512.|||||
||||<br>|||||
|**Decoder:**<br>Th|e decoder i|s also compose|d of a stack of|_ N_ = 6|identical|layers. In addit|ion to the two|
|sub-layers in e|ach encod|er layer, the de|coder inserts a|third|sub-layer,|which perform|s multi-head|
|attention over t|he output o|f the encoder s|tack. Similar to|the en|coder, we|employ residua|l connections|
|around each of|the sub-la|yers, followed|by layer norm|alizat|ion. We al|so modify the|self-attention|
|sub-layer in th|e decoder|stack to preve|nt positions fr|om att|ending to|subsequent po|sitions. This|
|masking, comb|ined with|fact that the ou|tput embeddin|gs are|offset by o|ne position, en|sures that the|
|predictions for|position_ i_|can depend on|ly on the know|n outp|uts at posi|tions less than|_ i_.|
|<br><br>|<br>|||||||
|**3.2**<br>**Attention**||||||||
|||||||||
|An attention fu|nction can|be described a|s mapping a q|uery a|nd a set of|key-value pair|s to an output,|
|where the quer|y, keys, va|lues, and outpu|t are all vector|s. The|output is|computed as a|weighted sum|



## Table 4 (page 4, 55x8)
|Sca|led Dot|-Product Attenti|on|Mu|lti-Head|Attention|Col8|
|---|---|---|---|---|---|---|---|
|<br>|<br>|<br>|<br>|<br>|<br>|<br>||
|Figure 2: (le|ft) Scal|ed Dot-Product|Attention. (rig|ht) Multi-Hea|d Attent|ion consis|ts of several|
|attention laye|rs runni|ng in parallel.||||||
|<br>|<br>|<br>||||||
|of the values,|where t|he weight assign|ed to each value|is computed b|y a comp|atibility fu|nction of the|
|query with th|e corres|ponding key.||||||
|<br><br>|<br>|<br>||||||
|**3.2.1**<br>**Scale**|**d Dot-P**|** roduct Attentio**|**  n**|||||
|<br>|<br>|<br>|<br>|||||
|We call our p|articula|r attention "Sca|led Dot-Product|Attention" (|Figure 2)|. The inp|ut consists of|
|queries and k<br>|eys of d<br>|imension_ dk_, an<br>  _√_|d values of dime<br>|nsion_ dv_. We<br>|compute<br>|the dot pr<br>|oducts of the<br>|
|query with al|l keys, d|ivide each by|_dk_, and apply a|softmax func|tion to ob|tain the w|eights on the|
|values.||||||||
|||||||||
|In practice, w|e comp|ute the attention|function on a s|et of queries|simultane|ously, pac|ked together|
|into a matrix|_ Q_. The|keys and values|are also packed|together into|matrices|_ K_ and_ V_ .|We compute|
|the matrix of|outputs|as:||||||
|||<br>||||||
|||||_QKT_<br>||||
|||||<br>||||
|||Attentio|n(_Q, K, V_ ) = s|ftmax(<br>~~_√_~~|)_V_||(1)|
|||||<br>_dk_||||
|||||||||
|The two most|commo|nly used attenti|on functions are|additive atten|tion [2],|and dot-pr|oduct (multi-|
|plicative) atte<br>|ntion. D|ot-product atten|tion is identical|to our algorit|hm, exce|pt for the|scaling factor|
|of<br>1<br>~~_√_~~ . Addi|tive atte|ntion computes|the compatibilit|y function usi|ng a feed|-forward|network with|
|_dk_   <br>|<br>|<br>|<br>|<br>|<br>|<br>|<br>|
|<br>a single hidd|en layer|. While the two|are similar in th|eoretical com|plexity,|ot-produc|t attention is|
|much faster a|nd more|space-efficient i|n practice, since|it can be imp|lemented|using hig|hly optimized|
|matrix multip|lication|code.||||||
|<br>|<br>|<br>||||||
|||||||||
|While for sm|ll valu|s of_ dk_ the two|mechanisms per|orm similarl|, additiv|attention|outperforms|
|||<br>||||||
|dot product a|tention|without scaling|for larger value|of_ dk_ [3]. W|e suspect|that for la|rge values of|
|||||<br>||||
|_dk_, the dot pr<br>|oducts g<br>|row large in ma<br>|nitude, pushing<br>|the softmax f<br>|unction i<br>|to region<br><br>|where it has|
|extremely sm|all grad|ents 4. To count|eract this effect,|we scale the|dot prod|cts by<br>1<br>~~_√_~~|.|
|||||||<br>_d_||
|||||||<br>|_k_|
|||||||||
|**3.2.2**<br>**Multi**|**-Head**|** Attention**||||||
|<br>|<br>|<br>||||||
|||||||||
|Instead of pe|formin|a single attenti|on function wit|_ d_model-dime|sional k|ys, value|and queries,|
|we found it b|eneficial|to linearly proj|ect the queries, k|eys and value|s_ h_ times|with diffe|rent, learned|
|||||||||
|linear project|ions to|_k_,_ dk_ and_ dv_ di|ensions, respe|tively. On ea|h of the|e projecte|d versions of|
|||<br>||||||
|queries, keys|and val|es we then perf|rm the attentio|function in|arallel, y|ielding_ dv_|-dimensional|
|||||||||
|4To illustrat<br>|e why th<br>|e dot products get<br>|large, assume that<br>|the component<br>|s of_ q_ and <br>|_ k_ are indep|endent random|
|variables with|ean 0 a|d variance 1. Th|n their dot produ|t,_ q · k_ =P_dk_<br>|_qk_, ha|mean 0 a|d variance_ d_.|
|||||<br>_i_=|1 _ii_||_k_|



## Table 5 (page 5, 65x6)
|output value|s. These are co|ncatenated an|d once again pro|jected, resulting in the|final values, as|
|---|---|---|---|---|---|
|depicted in F|igure 2.|||||
|<br>|<br>|||||
|Multi-head a|ttention allows t|he model to jo|intly attend to in|formation from different|representation|
|subspaces at|different positio|ns. With a sin|gle attention head|, averaging inhibits this|.|
||<br>|<br>|<br>|<br>||
||MultiH|ad(_Q, K, V_ )|Concat(head|_, ...,_ head)_W O_||
||||1|h||
|||||<br>||
|||||_Q_<br>  _ K_<br>  _ V_<br>||
|||where headi|Attention(_Q_|<br>_i , KW _<br>_i , V W _<br>_i_ )||
|||<br>||<br> <br> <br><br>||
|Where the pr<br>|ojections are par<br>|ameter matrice|s_ W Q_<br>_i_<br>_∈_R_d_model_×_|_dk_,_ W K_<br>_i_<br>_∈_R_d_model_×dk_,_ W_|_V_<br>_i_<br>_∈_R_d_model_×dv_|
|and_ W O ∈_R|_hdv×d_model.|||||
|||||||
|In this work|we employ _h_|= 8 parallel|attention layers,|or heads. For each o|f these we use|
|||||||
|_dk_ =_ dv_ =_ d_|model_/h_ = 64.|ue to the redu|ed dimension of|each head, the total co|putational cost|
|<br>is similar to t|hat of single-he|ad attention wi|th full dimensio|nality.||
|<br><br>|<br>|<br>|<br>|||
|**3.2.3**<br>**Appl**|**ications of Atte**|**  ntion in our M**|**     odel**|||
|<br>|<br>|<br>|<br>|||
|The Transfor|mer uses multi-|head attention|in three different|ways:||
|<br>|<br>|<br>|<br>|<br>||
|• In "|encoder-decode|r attention" la|yers, the queries|come from the previous|decoder layer,|
|and|the memory ke|ys and values|come from the o|utput of the encoder. Th|is allows every|
|pos|ition in the deco|der to attend o|ver all positions|in the input sequence. T|his mimics the|
|typi|cal encoder-dec|oder attention|mechanisms in|sequence-to-sequence|models such as|
|[38,|2, 9].|||||
|<br>|<br>|||||
|• The|encoder contai|ns self-attentio|n layers. In a se|lf-attention layer all of t|he keys, values|
|and|queries come fr|om the same p|lace, in this case|, the output of the previ|ous layer in the|
|enc|oder. Each posit|ion in the enco|der can attend to|all positions in the previ|ous layer of the|
|enc|oder.|||||
|||||||
|• Sim|ilarly, self-atten|tion layers in th|e decoder allow|each position in the deco|der to attend to|
|all p|ositions in the|decoder up to a|nd including tha|t position. We need to p|revent leftward|
|info|rmation flow in|the decoder to|preserve the auto|-regressive property. We|implement this|
|insi|de of scaled dot-|product attenti|on by masking ou|t (setting to_ −∞_) all val|ues in the input|
|of t|he softmax whic|h correspond t|o illegal connect|ions. See Figure 2.||
|<br><br>|<br>|<br>|<br>|||
|**3.3**<br>**Positio**|**n-wise Feed-Fo**|** rward Netwo**|**  rks**|||
|<br>|<br>|<br>|<br>|||
|In addition t|o attention sub-|layers, each of|the layers in ou|r encoder and decoder c|ontains a fully|
|connected fe|ed-forward netw|ork, which is|applied to each p|osition separately and i|dentically. This|
|consists of t|wo linear transfo|rmations with|a ReLU activatio|n in between.||
|||<br>|<br>|<br>||
|||||||
|||FFN(_x_) = m|ax(0_, xW_1 +_ b_1|)_W_2 +_ b_2|(2)|
||||<br>|<br>||
|While the lin|ear transformati|ons are the sam|e across different|positions, they use diffe|rent parameters|
|from layer t|o layer. Anoth|er way of des|cribing this is a|s two convolutions with|kernel size 1.|
|||||||
|The dimensi|onality of inpu|and output is|_d_model = 512,|nd the inner-layer has|dimensionality|
|||||||
|_dff_ = 2048.||||||
|<br><br>||||||
|**3.4**<br>**Embed**|**dings and Soft**|**  max**||||
|<br>|<br>|<br>||||
|Similarly to|other sequence|transduction m|odels, we use le|arned embeddings to co|nvert the input|
|||||||
|tokens and o|tput tokens to v|ectors of dime|sion_ d_model. We|lso use the usual learne|linear transfor-|
|mation and s|oftmax function|to convert the|decoder output t|o predicted next-token p|robabilities. In|
|our model, w<br>|e share the sam<br>|e weight matrix<br>|between the tw<br>|o embedding layers and t<br>|he pre-softmax<br>  _√_|
|linear transfo|rmation, similar|to [30]. In the|embedding layer|s, we multiply those wei|hts by _d_model.|



## Table 6 (page 6, 68x6)
|Table 1: Maxi|mum path length|s, per-layer comp|lexity and minimum|number of seque|ntial operations|
|---|---|---|---|---|---|
|for different la|yer types. _n_ is t|he sequence lengt|h,_ d_ is the represent|ation dimension|,_ k_ is the kernel|
|size of convolu|tions and_ r_ the|size of the neighb|orhood in restricted|self-attention.||
|<br>|<br>|<br>|<br> <br>|<br><br>||
|Layer Typ|e|Complexity pe|r Layer<br>Sequentia|l<br>Maximum P|ath Length|
||||Operation<br>|s||
|Self-Atten|tion|_O_(_n_2 _· d_<br>|)<br>_O_(1)<br>|_O_(|1)|
|Recurrent||_O_(_n · d_2<br>|)<br>_O_(_n_)<br>|_O_(|_n_)|
||||2<br>|||
|Convoluti|nal|_O_(_k · n · _|)<br>_O_(1)|_O_(_log_|_k_(_n_))|
|Self-Atten|tion (restricted)|_O_(_r · n · _|_ d_)<br>_O_(1)|_O_(_n_|_/r_)|
|<br><br>|<br>|||||
|**3.5**<br>**Position**|**al Encoding**|||||
|<br>|<br>|||||
|Since our mod|el contains no re|currence and no c|onvolution, in order|for the model to|make use of the|
|order of the se|quence, we must|inject some infor|mation about the re|lative or absolute|position of the|
|tokens in the s|equence. To thi|s end, we add "po|sitional encodings"|to the input em|beddings at the|
|||||||
|bottoms of the|encoder and dec|oder stacks. The|ositional encodings|have the same d|imension_ d_model|
|as the embeddi|ngs, so that the|two can be summ|ed. There are many|choices of positi|onal encodings,|
|learned and fix|ed [9].|||||
|<br>|<br>|||||
|In this work, w|e use sine and c|osine functions o|f different frequenci|es:||
|||<br>|<br>|<br>||
||||2_i/d_mod|el||
|||_PE_(_pos,_2_i_) =_ si_|_ n_(_pos/_10000|)||
|||<br>||||
||||2_i/d_mod|el||
|||_E_(_pos,_2_i_+1) =_ c_|_ s_(_pos/_10000|)||
|||<br>||||
|where_ pos_ is th|e position and_ i_|is the dimension.|That is, each dime|nsion of the posi|tional encoding|
|corresponds to|a sinusoid. The|wavelengths form|a geometric progres|sion from 2_π_ to|10000_ ·_ 2_π_. We|
|chose this fun|ction because w|e hypothesized it|would allow the m|odel to easily le|arn to attend by|
|||||||
|relative positi|ns, since for an|y fixed offset_ k_,|_ Epos_+_k_ can be rep|resented as a li|ear function of|
|||||||
|_PEpos_.||||||
|||||||
|We also experi|mented with usi|ng learned positio|nal embeddings [9]|instead, and fou|nd that the two|
|versions produ|ced nearly iden|tical results (see|Table 3 row (E)). W|e chose the sin|usoidal version|
|because it may|allow the mode|l to extrapolate to|sequence lengths l|onger than the on|es encountered|
|during training|.|||||
|<br><br>|<br>|||||
|**4**<br>**Why Se**|** lf-Attention**|||||
|<br>|<br>|||||
|In this section|we compare v|arious aspects of|self-attention layer|s to the recurre|nt and convolu-|
|tional layers c<br>|ommonly used f<br>|or mapping one v<br>|ariable-length sequ<br>|ence of symbol<br>|representations<br>|
|<br>|<br>|<br>|<br>|<br>   _d_|<br>|
|(_x_1_, ..., xn_) to|another sequen|ce of equal lengt|h (_z_1_, ..., zn_), with|_xi, zi ∈_, su|ch as a hidden|
|layer in a typic|al sequence tran|sduction encoder|or decoder. Motiva|<br>ting our use of s|elf-attention we|
|consider three|desiderata.|||||
|<br>|<br>|||||
|One is the tota|l computational|complexity per la|yer. Another is the|amount of comp|utation that can|
|be parallelized|, as measured b|y the minimum nu|mber of sequential|operations requi|red.|
|<br>|<br>|<br>|<br>|<br>|<br>|
|The third is th|e path length bet|ween long-range|dependencies in th|e network. Learn|ing long-range|
|dependencies i|s a key challeng|e in many sequen|ce transduction tas|ks. One key fact|or affecting the|
|ability to learn|such dependen|cies is the length|of the paths forwar|d and backward|signals have to|
|traverse in the|network. The s|horter these paths|between any comb|ination of positi|ons in the input|
|and output seq|uences, the easie|r it is to learn lon|g-range dependenci|es [12]. Hence w|e also compare|
|the maximum|path length betw|een any two inpu|t and output positio|ns in networks c|omposed of the|
|different layer|types.|||||
|<br>|<br>|||||
|As noted in Tab|le 1, a self-atten|tion layer connect|s all positions with a|constant numbe|r of sequentially|
|executed oper|ations, whereas|a recurrent layer|requires _O_(_n_) seq|uential operatio|ns. In terms of|
|computational|complexity, sel|f-attention layers|are faster than recu|rrent layers whe|n the sequence|
||||<br>|||
||||6|||



## Table 7 (page 7, 64x6)
|length n is smaller|than the re|presentation|dimensionality d, wh|ich is most often th|e case with|
|---|---|---|---|---|---|
|sentence representa|tions used by|state-of-the-|art models in machine|translations, such as|word-piece|
|[38] and byte-pair [|31] represen|tations. To im|prove computational|performance for tas|ks involving|
|very long sequences|, self-attenti|on could be re|stricted to considering|only a neighborhoo|d of size_ r_ in|
|the input sequence c|entered arou|nd the respec|tive output position. T|his would increase th|e maximum|
|path length to_ O_(_n/_|_r_). We plan|to investigat|e this approach further|in future work.||
|<br>|<br>|<br>|<br>|<br>||
|A single convolutio|nal layer wit|h kernel widt|h_ k < n_ does not con|nect all pairs of inpu|t and output|
|positions. Doing so|requires a st|ack of_ O_(_n/k_|) convolutional layers|in the case of contig|uous kernels,|
|||||||
|or_ O_(_logk_(_n_)) in t|e case of di|lated convol|tions [18], increasing|the length of the l|ngest paths|
|between any two po|sitions in th|e network. C|onvolutional layers ar|e generally more ex|pensive than|
|recurrent layers, by<br>|a factor of <br>|_k_. Separable<br>|convolutions [6], ho<br>|wever, decrease the<br>|complexity<br>|
|<br>considerably, to_ O_(|<br>_k · n · d_ +|<br>_ n · d_2). Even|<br> with_ k_ = _n_, however|<br>, the complexity of|<br>   a separable|
|convolution is equal|to the comb|ination of a s|elf-attention layer and|a point-wise feed-f|orward layer,|
|the approach we tak|e in our mo|del.||||
|<br>|<br>|<br>||||
|As side benefit, self-|attention cou|ld yield more|interpretable models.|We inspect attention|distributions|
|from our models an|d present an|d discuss exa|mples in the appendix.|Not only do individ|ual attention|
|heads clearly learn t|o perform di|fferent tasks,|many appear to exhibit|behavior related to|the syntactic|
|and semantic struct|ure of the se|ntences.||||
|<br><br>||||||
|**5**<br>**Training**||||||
|||||||
|This section describ|es the traini|ng regime for|our models.|||
|<br><br>|<br>|<br>||||
|**5.1**<br>**Training Dat**|** a and Batch**|**   ing**||||
|<br>|<br>|<br>||||
|We trained on the|standard W|MT 2014 En|glish-German dataset|consisting of about|4.5 million|
|sentence pairs. Sen|tences were|encoded usi|ng byte-pair encoding|[3], which has a sh|ared source-|
|target vocabulary of|about 3700|0 tokens. For|English-French, we us|ed the significantly|larger WMT|
|2014 English-Frenc|h dataset co|nsisting of 36|M sentences and split|tokens into a 32000|word-piece|
|vocabulary [38]. Se|ntence pairs|were batched|together by approximat|e sequence length. E|ach training|
|batch contained a s|et of senten|ce pairs conta|ining approximately|25000 source token|s and 25000|
|target tokens.||||||
|<br><br>||||||
|**5.2**<br>**Hardware an**|** d Schedule**|||||
|<br>|<br>|||||
|We trained our mo|dels on one|machine with|8 NVIDIA P100 GP|Us. For our base m|odels using|
|the hyperparameter|s described t|hroughout th|e paper, each training|step took about 0.4|seconds. We|
|trained the base mo|dels for a tot|al of 100,000|steps or 12 hours. For|our big models,(desc|ribed on the|
|bottom line of table|3), step tim|e was 1.0 sec|onds. The big models|were trained for 3|00,000 steps|
|(3.5 days).||||||
|<br><br>||||||
|**5.3**<br>**Optimizer**||||||
|||||||
|||||_−_9||
|We used the Adam|optimizer [2|0] with_ β_1 =|0_._9,_ β_2 = 0_._98 and_ ϵ_|= 10. We varied|the learning|
|rate over the course|of training,|<br>      according to|<br>        the formula:|||
|<br>|<br><br>|<br>|<br>|||
|_lrate_|=_ d−_0_._5<br> _·_|in(_stepnu_|_−_0_._5_, stepnum · wa_|_ rmupsteps−_1_._5)|(3)|
||<br>model|_|_|_||
|||||||
|This corresponds t|increasing|he learning r|te linearly for the fir|t_ warmupsteps_ tr|ining steps,|
|||||_||
|||||||
|and decreasing it t|ereafter pro|portionally t|the inverse square ro|ot of the step numb|er. We used|
|_warmupsteps_ =|000.|||||
|||||||
|_||||||
|||||||
|**5.4**<br>**Regularizatio**|**n**|||||
|||||||
|We employ three ty|pes of regula|rization duri|ng training:|||



## Table 8 (page 8, 61x6)
|Table 2: The Transform|er achieves better BL|EU scores|than previous|state-of-the-|art models on the|
|---|---|---|---|---|---|
|English-to-German and|English-to-French ne|wstest201|4 tests at a fra|ction of the tr|aining cost.|
|||<br>|<br>|<br>|<br>|
|||BLE|U|Training Cos|t (FLOPs)|
|Model||||<br>|<br>|
|||EN-DE<br>|EN-FR|EN-DE|EN-FR|
|ByteNet [18]||23.75||||
|Deep-Att + PosU|nk [39]||39.2||1_._0_ ·_ 1020<br>|
|GNMT + RL [38|]|24.6|39.92|2_._3_ ·_ 1019<br><br><br>|1_._4_ ·_ 1020<br>|
|ConvS2S [9]||25.16|40.46|9_._6_ ·_ 1018<br><br><br>|1_._5_ ·_ 1020<br>|
|MoE[32]||26.03|40.56|2_._0_ ·_ 1019<br>|1_._2_ ·_ 1020|
|Deep-Att + PosU|nk Ensemble [39]||40.4||8_._0_ ·_ 1020<br>|
|GNMT + RL En|semble [38]|26.30|41.16|1_._8_ ·_ 1020<br><br><br>|1_._1_ ·_ 1021<br>|
|ConvS2S Ensem|ble[9]|26.36|**41.29**|7_._7_ ·_ 1019<br>|1_._2_ ·_ 1021|
|Transformer (ba|se model)|27.3|38.1|**3****_._3****_ ·_ 1**<br>|** 018**<br>|
|Transformer (big|)|**28.4**|**41.8**|2_._3_ ·_ 1|019|
|<br>||||||
|**Residual Dropout**<br>W|e apply dropout [33] t|o the outpu|t of each sub|-layer, before|it is added to the|
|sub-layer input and norm|alized. In addition, w|e apply dr|opout to the s|ums of the em|beddings and the|
|positional encodings in|both the encoder and|decoder s|tacks. For th|e base model|, we use a rate of|
|||||||
|_Pdrop_ = 0_._1.||||||
|<br>||||||
|<br>||||||
|**Label Smoothing**<br>D|ring training, we em|ployed lab|el smoothin|of value_ ϵls_|= 0_._1 [36]. This|
|hurts perplexity, as the|model learns to be mo|re unsure,|but improves|<br>            accuracy and|BLEU score.|
|<br><br>||||||
|**6**<br>**Results**||||||
|||||||
|**6.1**<br>**Machine Transla**|** tion**|||||
|<br>|<br>|||||
|On the WMT 2014 Engl|ish-to-German transla|tion task, t|he big transfo|rmer model (|Transformer (big)|
|in Table 2) outperforms|the best previously re|ported mo|dels (includin|g ensembles)|by more than 2_._0|
|BLEU, establishing a n|ew state-of-the-art B|LEU score|of 28_._4. The|configuration|of this model is|
|listed in the bottom line|of Table 3. Training|took 3_._5 d|ays on 8 P10|0 GPUs. Eve|n our base model|
|surpasses all previously|published models an|d ensemble|s, at a fractio|n of the traini|ng cost of any of|
|the competitive models.||||||
|<br>||||||
|On the WMT 2014 Engl|ish-to-French translat|ion task, o|ur big model|achieves a BL|EU score of 41_._0,|
|outperforming all of the|previously published|single mo|dels, at less t|han 1_/_4 the tr|aining cost of the|
|previous state-of-the-ar|t model. The Transfo|rmer (big)|model train|ed for Englis|h-to-French used|
|||||||
|dropout rate_ Pdrop_ = 0_._|1, instead of 0_._3.|||||
|<br>||||||
|For the base models, w|e used a single mode|l obtained|by averaging|the last 5 ch|eckpoints, which|
|were written at 10-min|ute intervals. For the|big model|s, we average|d the last 20|checkpoints. We|
|used beam search with|a beam size of 4 and|length pen|alty_ α_ = 0_._6|[38]. These|hyperparameters|
|were chosen after experi|mentation on the deve|lopment se|t. We set the|maximum out|put length during|
|inference to input length|+ 50, but terminate e|arly when|possible [38|].||
|<br>|<br>|<br>|<br>|<br>||
|Table 2 summarizes our|results and compares|our translat|ion quality a|nd training co|sts to other model|
|architectures from the li|terature. We estimate|the numbe|r of floating|point operatio|ns used to train a|
|model by multiplying th<br>|e training time, the n<br>|umber of G<br>|PUs used, a|nd an estimat|e of the sustained|
|single-precision floating|-point capacity of eac|h GPU 5.||||
|<br><br>|<br>|||||
|**6.2**<br>**Model Variations**||||||
|<br>|<br>|||||
|To evaluate the importa|nce of different comp|onents of|the Transfor|mer, we varie|d our base model|
|in different ways, meas|uring the change in p|erformanc|e on English|-to-German t|ranslation on the|
|<br>|<br>|<br>|<br>|<br>|<br>|
|5We used values of 2.8|, 3.7, 6.0 and 9.5 TFLO|PS for K80,|K40, M40 and|P100, respecti|vely.|



## Table 9 (page 9, 68x8)
|Table 3: Variatio|ns on the Transf|ormer ar|chitecture.|Unlisted v|alues are iden|tical to those of|the base|
|---|---|---|---|---|---|---|---|
|model. All metr|ics are on the En|glish-to-|German tr|anslation d|evelopment s|et, newstest2013|. Listed|
|perplexities are|per-wordpiece, a|ccording|to our byt|e-pair enc|oding, and sh|ould not be com|pared to|
|per-word perple|xities.|||||||
|||||||||
||||||train<br>|PL<br>BLEU|params|
|||||||||
|_N_<br>|model<br>_d_ff<br>|_h_<br>_dk_|_dv_<br>|_drop_<br>_ϵl_|_s_<br><br>||6|
||||||steps<br>(|ev)<br>(dev)|_×_10|
|base<br>6<br>|512<br>2048|8<br>64|64|0.1<br>0.|1<br>100K<br>4|.92<br>25.8|65|
|||1<br>512|512||5|.29<br>24.9||
|||4<br>128|128|||.00<br>25.5||
|(A)||||||||
|||||||||
|||6<br>32|32|||.91<br>25.8||
|||32<br>16|16||5|.01<br>25.4||
|||16||||.16<br>25.1|58|
|||||||||
|(B)||||||||
|||32||||.01<br>25.4|60|
|2|||||6|.11<br>23.7|36|
|4|||||5|.19<br>25.3|50|
|8|||||4|.88<br>25.5|80|
|(C)<br>|256|32|32||5|.75<br>24.5|28|
|1|024|128|128||4|.66<br>26.0|168|
||1024||||5|.12<br>25.4|53|
||4096||||4|.75<br>26.2|90|
|||||0.0|5|.77<br>24.6||
|||||0.2||.95<br>25.5||
|||||||||
|(D)||||||||
|||||0.||.67<br>25.3||
|||||0.|2<br>5|.47<br>25.7||
|(E)|positional emb|edding i|nstead of s|inusoids|4|.92<br>25.7||
|big<br>6<br>1|024<br>4096<br>|16||0.3|300K<br>**4**|**.33**<br>**26.4**|213|
|||||||||
|development se|t, newstest2013.|We used|beam sea|rch as des|cribed in the|previous section|, but no|
|checkpoint aver|aging. We prese|nt these r|esults in T|able 3.||||
|<br>|<br>|<br>|<br>|<br>||||
|In Table 3 rows (|A), we vary the|number o|f attention|heads and|the attention k|ey and value dim|ensions|
|keeping the am|ount of comput|ation con|stant, as|described|in Section 3.|2.2. While sing|le-head|
|attention is 0.9|BLEU worse tha|n the bes|t setting, q|uality also|drops off wit|h too many head|s.|
|<br>|<br>|<br>|<br>|<br>|<br>|<br>|<br>|
|||||||||
|In Table 3 rows|(B), we observ|that re|ucing the|attention|ey size_ dk_ h|rts model quali|ty. This|
|suggests that d|etermining com|patibility|is not eas|y and tha|<br>t a more sop|histicated comp|atibility|
|function than do|t product may be|benefici|al. We furt|her observ|e in rows (C) a|nd (D) that, as e|xpected|
|bigger models ar|e better, and dro|pout is ve|ry helpful i|n avoiding|over-fitting. I|n row (E) we rep|lace our|
|sinusoidal posit|ional encoding w|ith learn|ed position|al embed|dings [9], and|observe nearly i|dentical|
|results to the ba|se model.|||||||
|<br><br>|<br>|||||||
|**6.3**<br>**English C**|** onstituency Pa**|**  rsing**||||||
|<br>|<br>|<br>||||||
|To evaluate if th|e Transformer c|an gener|alize to ot|her tasks|we performed|experiments on|English|
|constituency par|sing. This task p|resents s|pecific cha|llenges: th|e output is su|bject to strong st|ructural|
|constraints and|is significantly|longer t|han the in|put. Furth|ermore, RNN|sequence-to-s|equence|
|models have no|t been able to att|ain state-|of-the-art|results in s|mall-data reg|imes [37].||
|<br>|<br>|<br>|<br>|<br>|<br>|<br>||
|||||||||
|We trained a 4-l|yer transformer|with_ dmo_|_del_ = 102|on the|all Street Jour|nal (WSJ) porti|n of the|
|Penn Treebank|[25], about 40K|training|<br>    sentences.|We also t|rained it in a|semi-supervised|setting,|
|using the larger|high-confidence|and Berk|leyParser|corpora fr|om with appro|ximately 17M se|ntences|
|[37]. We used a|vocabulary of 1|6K token|s for the W|SJ only s|etting and a v|ocabulary of 32K|tokens|
|for the semi-sup|ervised setting.|||||||
|<br>|<br>|||||||
|We performed o|nly a small num|ber of ex|periments|to select th|e dropout, bo|th attention and|residual|
|(section 5.4), le|arning rates and|beam siz|e on the S|ection 22|development|set, all other par|ameters|
|remained uncha|nged from the|English-t|o-German|base tran|slation model|. During infere|nce, we|



## Table 10 (page 10, 63x9)
|T|able|4: The Transformer generalizes|w|ell to En|glish|constituency parsing|(Results are on Sectio|n 23|
|---|---|---|---|---|---|---|---|---|
|o|f W|SJ)|||||||
|||**Parser**||||**Training**|**WSJ 23 F1**||
|||Vinyals & Kaiser el al. (20|1|4) [37]|WSJ|only, discriminativ|e<br>88.3||
|||Petrov et al. (2006) [2|9|]|WSJ|only, discriminativ|e<br>90.4||
|||Zhu et al. (2013) [40|]||WSJ|only, discriminativ|e<br>90.4||
|||Dyer et al. (2016) [8|]||WSJ|only, discriminativ|e<br>91.7||
|||Transformer(4 layer|s)||WSJ|only, discriminativ|e<br>91.3||
|||Zhu et al. (2013) [40|]|||semi-supervised|91.3||
|||Huang & Harper (2009)|[|14]||semi-supervised|91.3||
|||McClosky et al. (2006)|[|26]||semi-supervised|92.1||
|||Vinyals & Kaiser el al. (20|1|4) [37]||semi-supervised|92.1||
|||Transformer(4 layer|s)|||semi-supervised|92.7||
|||Luong et al. (2015) [2|3|]||multi-task|93.0||
|||Dyer et al. (2016) [8|]|||generative|93.3||
|||<br>|||||||
|i|ncre|ased the maximum output length|to|input le|ngth|+ 300. We used a be|am size of 21 and_ α_ =|0_._3|
|f|or bo|th WSJ only and the semi-super|v|ised setti|ng.||||
|<br>|<br>|<br>|<br>|<br>|<br>||||
|O|ur r|esults in Table 4 show that des|pi|te the la|ck of|task-specific tunin|g our model performs|sur-|
|p|risin|gly well, yielding better results|th|an all pr|eviou|sly reported model|s with the exception o|f the|
|R|ecu|rrent Neural Network Grammar|[8|].|||||
|<br>|<br>|<br>|<br>|<br>|||||
|I|n co|ntrast to RNN sequence-to-sequ|en|ce mode|ls [3|7], the Transformer|outperforms the Berk|eley-|
|P|arse|r [29] even when training only o|n|the WSJ|train|ing set of 40K sente|nces.||
|<br>|<br><br>|<br>|||||||
|**7**||**Conclusion**|||||||
||||||||||
|I|n thi|s work, we presented the Transf|or|mer, the|first s|equence transductio|n model based entirel|y on|
|a|ttent|ion, replacing the recurrent layer|s|most co|mmo|nly used in encoder-|decoder architectures|with|
|m|ulti|-headed self-attention.|||||||
|<br>|<br>|<br>|||||||
|F|or tr|anslation tasks, the Transforme|r|can be t|raine|d significantly faste|r than architectures b|ased|
|o|n re|current or convolutional layers.||On both|WM|T 2014 English-to-|German and WMT 2|014|
|E|ngli|sh-to-French translation tasks,|w|e achieve|a ne|w state of the art. I|n the former task our|best|
|m|ode|l outperforms even all previousl|y|reported|ense|mbles.|||
|<br>|<br>|<br>|<br>|<br>|<br>|<br>|||
|W|e ar|e excited about the future of atte|nt|ion-base|d mo|dels and plan to app|ly them to other tasks|. We|
|p|lan t|o extend the Transformer to prob|le|ms invol|ving|input and output mo|dalities other than text|and|
|t|o inv|estigate local, restricted attentio|n|mechan|isms|to efficiently handl|e large inputs and out|puts|
|s|uch|as images, audio and video. Mak|in|g genera|tion l|ess sequential is ano|ther research goals of|ours.|
|<br>|<br>|<br>|<br>|<br>|<br>|<br>|<br>|<br>|
|T|he|code we used to train and ev|al|uate our|mo|dels is available at|`https://github.`|`com/`|
|`t`|`ens`|`orflow/tensor2tensor`.|||||||
||||||||||
|**A**|**ckn**|**owledgements**<br>We are gratef|ul|to Nal|Kalch|brenner and Stepha|n Gouws for their fru|itful|
|c|omm|ents, corrections and inspiration|.||||||
|<br>|<br>|<br>|||||||
|**R**|**efe**|**rences**|||||||
||||||||||
||[1]|Jimmy Lei Ba, Jamie Ryan Kiro|s,|and Geo|ffrey|E Hinton. Layer nor|malization. _arXiv pre_|_ print_|
|||_arXiv:1607.06450_, 2016.|||||||
|||<br>|||||||
||[2]|Dzmitry Bahdanau, Kyunghyun|Ch|o, and Y|oshu|a Bengio. Neural ma|chine translation by jo|intly|
|||learning to align and translate. _C_|_o_|_RR_, abs/|1409.|0473, 2014.|||
||<br>|<br>||<br>|<br>|<br>|||
||[3]|Denny Britz, Anna Goldie, Minh|-T|hang Lu|ong,|and Quoc V. Le. Ma|ssive exploration of n|eural|
|||machine translation architecture|s.|_CoRR_, a|bs/17|03.03906, 2017.|||
||<br>|<br>|<br>|<br>|<br>|<br>|||
||[4]|Jianpeng Cheng, Li Dong, and M|ir|ella Lap|ata. L|ong short-term mem|ory-networks for mac|hine|
|||reading. _arXiv preprint arXiv:16_|_  0_|_  1.06733_,|2016|.|||
||||||<br>||||
||||||10||||



## Table 11 (page 11, 63x6)
|[5]|Kyunghyun Cho, Bar|t van Merrienb|oer, Cagl|ar Gulcehre, Fethi Bougar|es, Holger Schwenk,|
|---|---|---|---|---|---|
||and Yoshua Bengio. L|earning phrase|represent|ations using rnn encoder-d|ecoder for statistical|
||machine translation.|_CoRR_, abs/1406|.1078, 20|14.||
||<br>|<br>|<br>|<br>||
|[6]|Francois Chollet. Xc|eption: Deep l|earning|with depthwise separable|convolutions. _arXiv_|
||_preprint arXiv:1610.0_|_ 2357_, 2016.||||
|||<br>||||
|[7]|Junyoung Chung, Çag|lar Gülçehre, K|yunghyun|Cho, and Yoshua Bengio.|Empirical evaluation|
||of gated recurrent neu|ral networks on|sequence|modeling. _CoRR_, abs/141|2.3555, 2014.|
||<br>|<br>|<br>|<br>|<br>|
|[8]|Chris Dyer, Adhigun|a Kuncoro, Mi|guel Ball|esteros, and Noah A. Smit|h. Recurrent neural|
||network grammars. In|_ Proc. of NAAC_|_   L_, 2016.|||
||<br>||<br>|||
|[9]|Jonas Gehring, Micha|el Auli, David|Grangier,|Denis Yarats, and Yann N|. Dauphin. Convolu-|
||tional sequence to seq|uence learning.|_arXiv pr_|_ eprint arXiv:1705.03122v2_|, 2017.|
||||||<br>|
|[10]|Alex Graves.<br>Gen|erating sequen|ces with|recurrent neural network|s.<br>_arXiv preprint_|
||_arXiv:1308.0850_, 201|3.||||
||<br>|<br>||||
|[11]|Kaiming He, Xiangy|u Zhang, Shao|qing Ren,|and Jian Sun. Deep resid|ual learning for im-|
||age recognition. In|_Proceedings of _|_the IEEE_|_Conference on Computer_|_Vision and Pattern_|
||_Recognition_, pages 77|0–778, 2016.||||
||<br>|<br>||||
|[12]|Sepp Hochreiter, Yos|hua Bengio, Pa|olo Frasc|oni, and Jürgen Schmidhub|er. Gradient flow in|
||recurrent nets: the dif|ficulty of learni|ng long-te|rm dependencies, 2001.||
||<br>|<br>|<br>|<br>||
|[13]|Sepp Hochreiter and|Jürgen Schmid|huber. L|ong short-term memory.|_Neural computation_,|
||9(8):1735–1780, 1997|.||||
||<br>|<br>||||
|[14]|Zhongqiang Huang a|nd Mary Harpe|r. Self-tra|ining PCFG grammars wi|th latent annotations|
||across languages. In|_ Proceedings of_|_   the 2009_|_     Conference on Empirical_|_        Methods in Natural_|
||_Language Processing_,|pages 832–841|. ACL, A|ugust 2009.||
||<br>|<br>|<br>|<br>||
|[15]|Rafal Jozefowicz, Ori|ol Vinyals, Mik|e Schust|er, Noam Shazeer, and Yon|ghui Wu. Exploring|
||the limits of language|modeling. _arX_|_iv preprin_|_ t arXiv:1602.02410_, 2016.||
||<br>|<br>||<br>||
|[16]|Łukasz Kaiser and Sa|my Bengio. Can|active m|emory replace attention? In|_ Advances in Neural_|
||_Information Processin_|_ g Systems, (NI_|_   PS)_, 2016|.||
||||<br>|<br>||
|[17]|Łukasz Kaiser and Ily|a Sutskever. Ne|ural GPU|s learn algorithms. In_ Inter_|_ national Conference_|
||_on Learning Represen_|_  tations (ICLR)_,|2016.|||
|||<br>|<br>|||
|[18]|Nal Kalchbrenner, Las|se Espeholt, Ka|ren Simo|nyan, Aaron van den Oord,|Alex Graves, and Ko-|
||ray Kavukcuoglu. Neu|ral machine tra|nslation in|linear time._ arXiv preprint_|_   arXiv:1610.10099v2_,|
||2017.|||||
|||||||
|[19]|Yoon Kim, Carl Dento|n, Luong Hoan|g, and Al|exander M. Rush. Structure|d attention networks.|
||In_ International Conf_|_  erence on Learn_|_    ing Repr_|_     esentations_, 2017.||
|||||<br>||
|[20]|Diederik Kingma and|Jimmy Ba. Ad|am: A me|thod for stochastic optimiz|ation. In_ ICLR_, 2015.|
|||||||
|[21]|Oleksii Kuchaiev and|Boris Ginsburg|. Factoriz|ation tricks for LSTM netw|orks. _arXiv preprint_|
||_arXiv:1703.10722_, 20|17.||||
||<br>|<br>||||
|[22]|Zhouhan Lin, Minw|ei Feng, Cicer|o Noguei|ra dos Santos, Mo Yu,|Bing Xiang, Bowen|
||Zhou, and Yoshua Be|ngio. A struct|ured self-|attentive sentence embedd|ing. _arXiv preprint_|
||_arXiv:1703.03130_, 20|17.||||
||<br>|<br>||||
|[23]|Minh-Thang Luong,|Quoc V. Le, Ilya|Sutskeve|r, Oriol Vinyals, and Luka|sz Kaiser. Multi-task|
||sequence to sequence|learning. _arXiv_|_ preprint_|_  arXiv:1511.06114_, 2015.||
||<br>|<br>||<br>||
|[24]|Minh-Thang Luong, H|ieu Pham, and|Christoph|er D Manning. Effective ap|proaches to attention-|
||based neural machine|translation. _ar_|_Xiv prepri_|_ nt arXiv:1508.04025_, 2015|.|



## Table 12 (page 12, 57x6)
|[25]|Mitchell P Marcus,|Mary Ann Marcinkiewic|z, and Beatric|e Santorini. Buildi|ng a large annotated|
|---|---|---|---|---|---|
||corpus of english: T|he penn treebank. _Com_|_putational li_|_ nguistics_, 19(2):31|3–330, 1993.|
||<br>|<br>||<br>|<br>|
|[26]|David McClosky, E|ugene Charniak, and M|ark Johnson.|Effective self-trai|ning for parsing. In|
||_Proceedings of the H_|_   uman Language Techn_|_     ology Confer_|_      ence of the NAACL_|_         , Main Conference_,|
||pages 152–159. AC|L, June 2006.||||
||<br>|<br>||||
|[27]|Ankur Parikh, Oscar|Täckström, Dipanjan D|as, and Jakob|Uszkoreit. A deco|mposable attention|
||model. In_ Empirical_|_  Methods in Natural La_|_     nguage Proc_|_      essing_, 2016.||
||<br>|||<br>||
|[28]|Romain Paulus, Cai|ming Xiong, and Richa|rd Socher. A|deep reinforced m|odel for abstractive|
||summarization. _arX_|_iv preprint arXiv:1705._|_  04304_, 2017.|||
||||<br>|||
|[29]|Slav Petrov, Leon|Barrett, Romain Thiba|ux, and Dan|Klein. Learning|accurate, compact,|
||and interpretable tr|ee annotation. In _Pro_|_ceedings of t_|_he 21st Internatio_|_nal Conference on_|
||_Computational Ling_|_ uistics and 44th Annu_|_    al Meeting of_|_       the ACL_, pages 4|33–440. ACL, July|
||2006.|||||
|||||||
|[30]|Ofir Press and Lior|Wolf. Using the outpu|t embedding|to improve langu|age models. _arXiv_|
||_preprint arXiv:1608_|_ .05859_, 2016.||||
|||<br>||||
|[31]|Rico Sennrich, Barr|y Haddow, and Alexand|ra Birch. Ne|ural machine transl|ation of rare words|
||with subword units.|_arXiv preprint arXiv:1_|_  508.07909_, 2|015.||
||<br>||<br>|<br>||
|[32]|Noam Shazeer, Azal|ia Mirhoseini, Krzyszto|f Maziarz, A|ndy Davis, Quoc L|e, Geoffrey Hinton,|
||and Jeff Dean. Out|rageously large neural|networks: T|he sparsely-gated|mixture-of-experts|
||layer. _arXiv preprin_|_ t arXiv:1701.06538_, 20|17.|||
|||<br>|<br>|||
|[33]|Nitish Srivastava, G|eoffrey E Hinton, Alex|Krizhevsky, I|lya Sutskever, and|Ruslan Salakhutdi-|
||nov. Dropout: a sim|ple way to prevent neu|ral networks|from overfitting. _J_|_ournal of Machine_|
||_Learning Research_,|15(1):1929–1958, 2014|.|||
||<br>|<br>|<br>|||
|[34]|Sainbayar Sukhbaat|ar, Arthur Szlam, Jaso|n Weston, a|nd Rob Fergus. E|nd-to-end memory|
||networks. In C. Co|rtes, N. D. Lawrence,|D. D. Lee, M|. Sugiyama, and|R. Garnett, editors,|
||_Advances in Neural_|_   Information Processing_|_     Systems 28_,|pages 2440–2448.|Curran Associates,|
||Inc., 2015.|||||
||<br>|||||
|[35]|Ilya Sutskever, Orio|l Vinyals, and Quoc V|V Le. Seque|nce to sequence le|arning with neural|
||networks. In_ Advan_|_ ces in Neural Informati_|_    on Processin_|_     g Systems_, pages 3|104–3112, 2014.|
||<br>|||<br>|<br>|
|[36]|Christian Szegedy,|Vincent Vanhoucke, Se|rgey Ioffe, Jo|nathon Shlens, an|d Zbigniew Wojna.|
||Rethinking the ince|ption architecture for co|mputer visio|n. _CoRR_, abs/1512|.00567, 2015.|
||<br>|<br>|<br>|<br>|<br>|
|[37]|Vinyals & Kaiser,|Koo, Petrov, Sutskever,|and Hinton.|Grammar as a fo|reign language. In|
||_Advances in Neural_|_   Information Processing_|_     Systems_, 20|15.||
||||<br>|<br>||
|[38]|Yonghui Wu, Mike|Schuster, Zhifeng Ch|en, Quoc V|Le, Mohammad|Norouzi, Wolfgang|
||Macherey, Maxim K|rikun, Yuan Cao, Qin G|ao, Klaus Ma|cherey, et al. Goog|le’s neural machine|
||translation system:|Bridging the gap betwe|en human an|d machine translat|ion. _arXiv preprint_|
||_arXiv:1609.08144_, 2|016.||||
||<br>|<br>||||
|[39]|Jie Zhou, Ying Cao|, Xuguang Wang, Pen|g Li, and W|ei Xu. Deep recu|rrent models with|
||fast-forward connec|tions for neural machin|e translation.|_CoRR_, abs/1606.0|4199, 2016.|
||<br>|<br>|<br>|<br>|<br>|
|[40]|Muhua Zhu, Yue Z|hang, Wenliang Chen,|Min Zhang,|and Jingbo Zhu.|Fast and accurate|
||shift-reduce constitu|ent parsing. In_ Proceed_|_ ings of the 51_|_    st Annual Meeting_|_       of the ACL (Volume_|
||_1: Long Papers)_, pa|ges 434–443. ACL, Au|gust 2013.|||



## Table 13 (page 13, 14x10)
|Attention V|isualization|s|Col4|Col5|Col6|Col7|Col8|Col9|Col10|
|---|---|---|---|---|---|---|---|---|---|
|||<br>||||||||
|||ts||||||||
|||n||||n||||
||y|an<br>me||||atio<br>s<br>t|>|||
||it<br><br>orit|eric<br>ern<br>e|sed<br>|s|e<br>9<br>king|str<br>ng<br>ces<br>e<br>cul|OS<br>d><br>d><br>d>|d><br>d>|d>|
|It<br>is<br>in<br>this|spir<br>that<br>a<br>maj<br>of|Am<br>gov<br>hav|pas<br>new|law|sinc<br>200<br>ma<br>the|regi<br>or<br>voti<br>pro<br>mor<br>diffi|.<br><E<br><pa<br><pa<br><pa|<pa<br><pa|<pa|
|||||||||||
|It<br>is<br>in<br>this|spirit<br>that<br>a<br>majority<br>of|American<br>governments<br>have|passed<br>new|laws|since<br>2009<br>making<br>the|registration<br>or<br>voting<br>process<br>more<br>difficult|.<br><EOS><br><pad><br><pad><br><pad>|<pad><br><pad>|<pad>|
|||||||||||
|Figure 3: An|example of th|e attenti|on me|ch|anism follo|wing long-distance|dependencie|s in|the|
|encoder self-at|tention in layer|5 of 6.|Many|of|the attentio|n heads attend to a|distant depen|dency|of|
|the verb ‘maki|ng’, completin|g the phr|ase ‘m|ak|ing...more|difficult’. Attention|s here shown|only|for|
|the word ‘mak|ing’. Different|colors re|prese|nt d|ifferent he|ads. Best viewed in|color.|||



## Table 14 (page 14, 21x13)
|Col1|Col2|Col3|Col4|tion|Col6|Col7|Col8|Col9|Col10|g|Col12|Col13|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|||ct||a<br>d||||||n|n|><br>>|
|||er<br>e||lic<br>ul||||t||si|io|S<br>d|
|e<br>w|ll|v<br><br>rf|t<br>|p<br>o<br>|st||s|ha<br>|e<br>|s|y<br>in|O<br>a|
|h<br>a|wi|e<br>e<br>e|u<br>ts|p<br>h<br>e|u||hi<br>s|w<br>|r<br>|m|n<br>m<br>p|E<br>p|
|T<br>L||n<br>b<br>p<br>|,<br>b<br>i|a<br>s<br>b|j|-|t<br>i||a<br>||,<br>i<br><br>o<br>.|<<br><|
||||||||||||||
|The<br>Law|will|never<br>be<br>perfect<br>|,<br>but<br>its|application<br>should<br>be|just|-|this<br>is|what<br>|we<br>are<br>|missing|,<br>in<br>my<br>opinion<br>.|<EOS><br><pad>|
||||||||||||||
|||||tion||||||g|||
|||ct||a<br>d||||||n|n|><br>|
|||er<br>e||lic<br>ul||||t||si|io|S<br>d|
|e<br>w|ll|v<br><br>rf|t<br>|p<br>o<br>|st||s|ha|e<br>e|s|y<br>in|O<br>|
|h<br>a|wi|e<br>e<br>e|u<br>ts|p<br>h<br>e|u||hi<br>s|w|w<br>r|mi|n<br>m<br>p|E<br>|
|T<br>L||n<br>b<br>p|,<br>b<br>i|a<br>s<br>b|j|-|t<br>i||a||,<br>i<br><br>o<br>.|<<br>|
||||||||||||||
|The<br>Law|will|never<br>be<br>perfect|,<br>but<br>its|application<br>should<br>be|just|-|this<br>is|what|we<br>are|missing|,<br>in<br>my<br>opinion<br>.|<EOS><br><d>|
||||||||||||||
|re 4:|Two|attention he|ads, also|in layer 5|of|6, ap|parentl|y in|volved|in|anaphora resoluti|on. To|
|atten|tions|for head 5.|Bottom:|Isolated a|tten|tion|s from|just|the wo|rd|‘its’ for attention|heads|
|6. No|te th|at the attenti|ons are v|ery sharp|for|this|word.||||||



## Table 15 (page 15, 21x20)
|Col1|Col2|Col3|Col4|Col5|Col6|Col7|Col8|tion|Col10|Col11|Col12|Col13|Col14|Col15|Col16|g|Col18|Col19|Col20|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|||||t||||a|d|||||||n||n|><br>>|
||||er||e|||lic|ul||||t|||si||io|S<br>d|
|e|w|ll|v|f|r|t||p|o||st||s<br>ha|e|e|s||y<br>in|O<br>a|
|h|a|wi|e|e<br>||u|ts|p|h|e|u||s<br>w|w|r|mi|n|m<br>p|E<br>p|
|T|L||n|b<br>|,|b|i|a|s|b|j|-<br>t|i<br>||a|,|i|o|.<br><<br><|
|||||||||||||||||||||
|The|Law|will|never|be<br>ft|perec<br>,|but|its|application|should|be|just|-<br>thi|s<br>is<br>what|we|are|missing<br>,|in|my<br>opinion|.<br><EOS><br><pad>|
|||||||||||||||||||||
|||||||||tion||||||||g||||
|||||t||||a|d|||||||n||n|><br>>|
||||er|e||||lic|ul||||t|||si||io|S<br>d|
|e|w|ll|v|rf||t||p|o||st||s<br>ha|e|e|s||y<br>in|O<br>a|
|h|a|wi|e|e<br>||u|ts|p|h|e|u||s<br>w|w|r|mi|n|m<br>p|E<br>p|
|T|L||n|b<br>|,|b|i|a|s|b|j|-<br>t|i<br>||a|,|i|o|.<br><<br><|
|||||||||||||||||||||
|The|Law|will|never|be<br>erfect|p<br>,|but|its|application|should|be|just|-<br>thi|s<br>is<br>what|we|are|missing<br>,|in|my<br>opinion|.<br><EOS><br><pad>|
|||||||||||||||||||||
|ure|5:|Ma|ny o|f the|atten|tion|he|ads|ex|hibi|t be|havi|our that s|eem|s|related|to t|he str|ucture of the|
|enc|e.|We|give|two|such e|xa|mple|s a|bov|e, fr|om|two|different|head|s f|rom the|enc|oder|self-attention|
|yer|5|of 6|. Th|e he|ads cl|earl|y le|arn|ed t|o pe|rfo|rm d|ifferent ta|sks|.|||||



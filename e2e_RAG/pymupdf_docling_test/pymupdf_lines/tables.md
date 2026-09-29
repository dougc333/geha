# pymupdf_lines: 6 tables from 1706.03762v7.pdf

## Table 1 (page 9, 8x3)
|Col1|train<br>N d d h d d P ϵ<br>model ff k v drop ls steps|PPL BLEU params<br>(dev) (dev) ×106|
|---|---|---|
|base|6<br>512<br>2048<br>8<br>64<br>64<br>0.1<br>0.1<br>100K|4.92<br>25.8<br>65|
|(A)|1<br>512<br>512<br>4<br>128<br>128<br>16<br>32<br>32<br>32<br>16<br>16|5.29<br>24.9<br>5.00<br>25.5<br>4.91<br>25.8<br>5.01<br>25.4|
|(B)|16<br>32|5.16<br>25.1<br>58<br>5.01<br>25.4<br>60|
|(C)|2<br>4<br>8<br>256<br>32<br>32<br>1024<br>128<br>128<br>1024<br>4096|6.11<br>23.7<br>36<br>5.19<br>25.3<br>50<br>4.88<br>25.5<br>80<br>5.75<br>24.5<br>28<br>4.66<br>26.0<br>168<br>5.12<br>25.4<br>53<br>4.75<br>26.2<br>90|
|(D)|0.0<br>0.2<br>0.0<br>0.2|5.77<br>24.6<br>4.95<br>25.5<br>4.67<br>25.3<br>5.47<br>25.7|
|(E)|positional embedding instead of sinusoids|4.92<br>25.7|
|big|6<br>1024<br>4096<br>16<br>0.3<br>300K|**4.33**<br>**26.4**<br>213|



## Table 2 (page 10, 6x3)
|Parser|Training|WSJ 23 F1|
|---|---|---|
|Vinyals & Kaiser el al. (2014) [37]<br>Petrov et al. (2006) [29]<br>Zhu et al. (2013) [40]<br>Dyer et al. (2016) [8]|WSJ only, discriminative<br>WSJ only, discriminative<br>WSJ only, discriminative<br>WSJ only, discriminative|88.3<br>90.4<br>90.4<br>91.7|
|Transformer(4 layers)|WSJ only, discriminative|91.3|
|Zhu et al. (2013) [40]<br>Huang & Harper (2009) [14]<br>McClosky et al. (2006) [26]<br>Vinyals & Kaiser el al. (2014) [37]|semi-supervised<br>semi-supervised<br>semi-supervised<br>semi-supervised|91.3<br>91.3<br>92.1<br>92.1|
|Transformer(4 layers)|semi-supervised|92.7|
|Luong et al. (2015) [23]<br>Dyer et al. (2016) [8]|multi-task<br>generative|93.0<br>93.3|



## Table 3 (page 13, 9x39)
|Col1|Col2|Col3|Col4|Col5|Col6|Col7|Col8|Col9|Col10|Col11|Col12|Col13|Col14|Col15|Col16|Col17|Col18|Col19|Col20|Col21|Col22|Col23|Col24|Col25|Col26|Col27|Col28|Col29|Col30|Col31|Col32|Col33|Col34|Col35|Col36|Col37|Col38|Col39|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
||||||||||||||||||||||||||||||||||||||||
||||||||||||||||||||||||||||||||||||||||
|||||||||||||||||ts|||||||||||||||||||||||
|||||||||||||||n|n|en|||||||||on||||||||||||||
||||||||||||ty|||ca|ca|m||d|||||g||ati|||s||t||>|||||||
|||||||t|t||||ori|||ri|ri|ern|e|se|||e|9|in||str||ng|es|e|ul||S|d>|d>|d>|d>|d>|d>|
||||||is|iri|iri|at|at||aj|||me|me|ov|av|as|ew|ws|nc|00|ak|e|gi||ti|oc|or|ffic||EO|pa|pa|pa|pa|pa|pa|
|It|It|is|is|in|th|sp|sp|th|th|a|m|of|of|A|A|g|h|p|n|la|si|2|m|th|re|or|vo|pr|m|di|.|<|<|<|<|<|<|<|



## Table 4 (page 13, 8x33)
|It|is|in|is|rit|at|a|ty|of|n|ts|e|d|w|s|e|9|g|e|n|or|g|ss|re|ult|.|>|>|>|>|>|>|>|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
||||th|pi|th||ori||ica|en|av|se|ne|aw|inc|00|kin|th|tio||tin|e|o|ic||OS|ad|ad|ad|ad|ad|ad|
|||||s|||aj||er|m|h|as||l|s|2|a||tra||vo|roc|m|iff||E|<p|<p|<p|<p|<p|<p|
||||||||m||m|rn||p|||||m||gis|||p||d||<|||||||
||||||||||A|ve|||||||||re||||||||||||||
|||||||||||go|||||||||||||||||||||||
||||||||||||||||||||||||||||||||||
||||||||||||||||||||||||||||||||||



## Table 5 (page 14, 14x56)
|Col1|Col2|Col3|Col4|Col5|Col6|Col7|Col8|Col9|Col10|Col11|Col12|Col13|Col14|Col15|Col16|Col17|Col18|Col19|Col20|Col21|Col22|Col23|Col24|Col25|Col26|Col27|Col28|Col29|Col30|Col31|Col32|Col33|Col34|Col35|Col36|Col37|Col38|Col39|Col40|Col41|Col42|Col43|Col44|Col45|Col46|Col47|Col48|Col49|Col50|Col51|Col52|Col53|Col54|Col55|Col56|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|The|The|Law|Law|will|will|never|never|be|be|perfect|perfect|,|,|but|but|its|its|application|should|should|be|be|just|just|-|-|this|this|is|is|what|what|we|we|are|missing|missing|missing|,|,|in|in|my|my|my|opinion|opinion|opinion|.|.|.|<EOS>|<EOS>|<pad>|<pad>|
|||||||||||||||||||||||||||||||||||||||||||||||||||||||||
|||||||||||||||||||||||||||||||||||||||||||||||||||||||||
|The|The|Law|Law|will|will|never|never|be|be|perfect|perfect|,|,|but|but|its|its|lication|should|should|be|be|just|just|-|-|this|this|is|is|what|what|we|we|are|missing|missing|missing|,|,|in|in|my|my|my|opinion|opinion|opinion|.|.|.|<EOS>|<EOS>|<pad>|<pad>|
|The||||||||||||||||||app||||||||||||||||||||||||||||||||||||||
|||||||||||||||||||||||||||||||||||||||||||||||||||||||||
|||||||||||||||||||on||||||||||||||||||||||||||||||||||||||
|The|The|Law|Law|will|will|never|never|be|be|perfect|perfect|,|,|but|but|its|its|applicati|should|should|be|be|just|just|-|-|this|this|is|is|what|what|we|we|are|are|missing|missing|missing|,|,|in|in|my|my|my|opinion|opinion|opinion|.|.|.|<EOS>|<EOS>|<pad>|
|||||||||||||||||||||||||||||||||||||||||||||||||||||||||
|||||||||||||||||||||||||||||||||||||||||||||||||||||||||
|The|The|Law|Law|will|will|never|never|be|be|perfect|perfect|,|,|but|but|its|its|plication|should|should|be|be|just|just|-|-|this|this|is|is|what|what|we|we|are|are|missing|missing|missing|,|,|in|in|my|my|my|opinion|opinion|opinion|.|.|.|<EOS>|<EOS>|<pad>|
|||||||||||||||||||ap||||||||||||||||||||||||||||||||||||||
|ure<br>l att<br> 6.|ure<br>l att<br> 6.|4:  <br> ent<br>Not|4:  <br> ent<br>Not|Two<br> ions<br>e t|Two<br> ions<br>e t|att<br>  for<br> at t|att<br>  for<br> at t|enti<br>   he<br>  e|enti<br>   he<br>  e|on<br>   ad 5<br>   tte|on<br>   ad 5<br>   tte|hea<br>    . B<br>   tio|hea<br>    . B<br>   tio|ds, a<br>otto<br>   s|ds, a<br>otto<br>   s|lso<br>m: <br>    re|lso<br>m: <br>    re|in<br> Iso<br>     er|laye<br>late<br>      sh|laye<br>late<br>      sh|r 5<br>d at<br>      rp|r 5<br>d at<br>      rp|of 6<br> ten<br>       or|of 6<br> ten<br>       or|, ap<br> tion<br>        his|, ap<br> tion<br>        his|par<br> s fr<br>         wo|par<br> s fr<br>         wo|ent<br>  om<br>         d.|ent<br>  om<br>         d.|ly i<br>   jus|ly i<br>   jus|nvol<br>   t th|nvol<br>   t th|ved<br>    e wo|ved<br>    e wo|in<br>     rd ‘|in<br>     rd ‘|in<br>     rd ‘|ana<br>      its’|ana<br>      its’|pho<br>       for|pho<br>       for|ra r<br>        att|ra r<br>        att|ra r<br>        att|esol<br>        enti|esol<br>        enti|esol<br>        enti|utio<br>        on|utio<br>        on|utio<br>        on|n. <br>         hea|n. <br>         hea|Top<br>         ds 5|



## Table 6 (page 15, 11x48)
|Col1|Col2|Col3|Col4|Col5|Col6|Col7|Col8|Col9|Col10|Col11|Col12|Col13|Col14|Col15|Col16|Col17|Col18|Col19|Col20|Col21|Col22|Col23|Col24|Col25|Col26|Col27|Col28|Col29|Col30|Col31|Col32|Col33|Col34|Col35|Col36|Col37|Col38|Col39|Col40|Col41|Col42|Col43|Col44|Col45|Col46|Col47|Col48|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|The|The|Law|Law|will|will|never|never|be|be|perfect|perfect|,|,|but|but|its|its|application|application|should|should|be|just|just|-|-|this|is|what|what|we|are|missing|missing|,|in|in|my|my|opinion|opinion|.|.|<EOS>|<EOS>|<pad>|<pad>|
|||||||||||||||||||||||||||||||||||||||||||||||||
|||||||||||||||||||||||||||||||||||||||||||||||||
|The|The|Law|Law|will|will|never|never|be|be|perfect|perfect|,|,|but|but|its|its|lication|lication|should|should|be|just|just|-|-|this|is|what|what|we|are|missing|missing|,|in|in|my|my|opinion|opinion|.|.|<EOS>|<EOS>|<pad>|<pad>|
|The||||||||||||||||||app||||||||||||||||||||||||||||||
|||||||||||||||||||||||||||||||||||||||||||||||||
|The|The|Law|Law|will|will|never|never|be|be|perfect|perfect|,|,|but|but|its|its|application|application|should|should|be|just|just|-|-|this|is|what|what|we|are|missing|missing|,|in|in|my|my|opinion|opinion|.|.|<EOS>|<EOS>|<pad>|<pad>|
|||||||||||||||||||||||||||||||||||||||||||||||||
|||||||||||||||||||||||||||||||||||||||||||||||||
|The<br>ure<br>|The<br>ure<br>|Law<br> 5:  <br>|Law<br> 5:  <br>|will<br>Ma<br>|will<br>Ma<br>|never<br>ny<br>|never<br>ny<br>|be<br> of t<br>|be<br> of t<br>|perfect<br>  he a<br>|perfect<br>  he a<br>|,<br>   tten<br>|,<br>   tten<br>|but<br>   tio<br>|but<br>   tio<br>|its<br>   n h<br>|its<br>   n h<br>|application<br>    ead<br>|application<br>    ead<br>|should<br>    s ex<br>|should<br>    s ex<br>|be<br>     hib<br>|just<br>     it b<br>|just<br>     it b<br>|-<br>      eha<br>|-<br>      eha<br>|this<br>      vio<br>|is<br>      ur t<br>|what<br>       hat<br>|what<br>       hat<br>|we<br>        see<br>|are<br>        ms<br>|missing<br>         rela<br>|missing<br>         rela<br>|,<br>         ted<br>|in<br>          to t<br>|in<br>          to t<br>|my<br>           he<br>|my<br>           he<br>|opinion<br>            stru<br>|opinion<br>            stru<br>|.<br>            ctu<br>|.<br>            ctu<br>|<EOS><br>            re o<br>|<EOS><br>            re o<br>|<pad><br>             f th<br>|<pad><br>             f th<br>|



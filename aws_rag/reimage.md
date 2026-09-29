# Figures to re-describe

**Status (2026-09-29): all 73 re-described with the description-first prompt; 0
degenerate left.** Kept as the record of which figures were affected.

73 of the 2,112 figure descriptions (3.5%), in 47 papers, are
degenerate: Nova Lite transcribed the figure's labels, then repeated empty
`|` separators until it hit its token limit and never wrote the description.
The figures are still found by search (their labels and captions are indexed),
but the chatbot can't answer questions about what they show, e.g. which curve
is lowest (f06, XGBoost Figure 3).

The images themselves are fine; only the text description needs redoing. Found
with this check on `local_ingest/out/figures/*/figures.json`: a description
shorter than 40 characters, or 12+ empty `|` separators in a row.

To redo them (default model is Nova Lite; Nova Pro reads diagrams better), per paper:

```bash
FIGURE_MODEL_ID=us.amazon.nova-pro-v1:0 uv run --with boto3 --with 'botocore[crt]' \
  python local_ingest/describe_figures.py <document id> --redo --files <file>,<file> --upload
```

Images: `local_ingest/out/figures/<document id>/<file>` on the laptop and
`s3://sam-app-chunks-669059827483/figures/<document id>/<file>`.


## Community detection in graphs (0906.0612)

Document id `cbf155b2550a934ec67650aee9add18de8c89cecead8d81f8c609ef8b1818ae2` · 2 figures

| Page | File | Caption |
|---|---|---|
| 14 | `p014_f08.png` | FIG. 8 A dendrogram, or hierarchical tree. Horizontal cuts correspond to partitions of the graph in communi… |
| 41 | `p041_f16.png` | FIG. 16 Low-dimensional visualization of the modularity landscape for the metabolic network of the spiroche… |

## Deep Inside Convolutional Networks: Visualising Image Classification Models and Saliency Maps (1312.6034)

Document id `fa812c1af4df881c4ddd94d5435f740d0695eb9e6ebc0f378adde48f3d7a7f65` · 1 figure

| Page | File | Caption |
|---|---|---|
| 5 | `p005_f02.png` | Figure 2: Image-specific class saliency maps for the top-1 predicted class in ILSVRC-2013 test images. The… |

## ImageNet Large Scale Visual Recognition Challenge (1409.0575)

Document id `b8643541df1b287cdb35bc70741fa7c330c3be517e48f6b20eba7e995ddc8199` · 1 figure

| Page | File | Caption |
|---|---|---|
| 12 | `p012_f04.png` | Fig. 4 Random selection of images in ILSVRC detection validation set. The images in the top 4 rows were tak… |

## Going Deeper with Convolutions (1409.4842)

Document id `ba83bd105ffa669ccb2aa240d3176b8cb1c98355257ddee8e64aa486d5ade92a` · 1 figure

| Page | File | Caption |
|---|---|---|
| 7 | `p007_f04.png` | Figure 3: GoogLeNet network with all the bells and whistles |

## Conditional Generative Adversarial Nets (1411.1784)

Document id `678f3fc5c4d229a0b7c0386e3dcbc87b65eed9fcba02a9802fdb9a66451b7a81` · 1 figure

| Page | File | Caption |
|---|---|---|
| 3 | `p003_f01.png` | Figure 1: Conditional adversarial net |

## Deep Learning Face Attributes in the Wild (1411.7766)

Document id `4056eeb2f31b15fdd2b9c3ae59233ea2a06fd7f4f04294d9d2a7e8cf476d51c9` · 1 figure

| Page | File | Caption |
|---|---|---|
| 11 | `p011_f14.png` | Figure 14. More results of LNet averaged response maps. (Best viewed in color) |

## Image Super-Resolution Using Deep Convolutional Networks (1501.00092)

Document id `d0bf3b1b84bc9b6c540a96e52f3f157bae02b5390a9ac4df5b793efe65fdd02e` · 1 figure

| Page | File | Caption |
|---|---|---|
| 9 | `p009_f10.png` | Fig. 10. The test convergence curve of SRCNN and results of other methods on the Set5 dataset. |

## Show, Attend and Tell: Neural Image Caption Generation with Visual Attention (1502.03044)

Document id `d57e998f6805287eaee18657e67df990f75d79367af9fda204560db4655752db` · 1 figure

| Page | File | Caption |
|---|---|---|
| 11 | `p011_f14.png` | (b) A woman is throwing a frisbee in a park. Figure 6. |

## Fast R-CNN (1504.08083)

Document id `a6bebb46b58dfdc89ff28f7bd577c314ba4132f6d7e264c6f39befb0cd496191` · 1 figure

| Page | File | Caption |
|---|---|---|
| 8 | `p008_f03.png` | Figure 3. VOC07 test mAP and AR for various proposal schemes. |

## Dropout as a Bayesian Approximation: Representing Model Uncertainty in Deep Learning (1506.02142)

Document id `dcebe17f1cef7d510900659c23d68038e5c6f9aaca2949f40bf91edd10566bca` · 1 figure

| Page | File | Caption |
|---|---|---|
| 8 | `p008_f06.png` | Figure 5. Depiction of the reinforcement learning problem used in the experiments. The agent is in the lowe… |

## Rethinking the Inception Architecture for Computer Vision (1512.00567)

Document id `80e30acdfa89bcb41a00c8b221cb9a1dc44256897e75af8762f171ec9dc77b85` · 1 figure

| Page | File | Caption |
|---|---|---|
| 3 | `p003_f01.png` | Figure 1. Mini-network replacing the 5 × 5 convolutions. |

## "Why Should I Trust You?": Explaining the Predictions of Any Classifier (1602.04938)

Document id `365079753571d7d14180e9796cf5d8ae53c5ef157f0a585ef8030b2a126eeccb` · 2 figures

| Page | File | Caption |
|---|---|---|
| 5 | `p005_f08.png` | Covered Features Figure 5: Toy example W . Rows represent instances (documents) and columns represent featu… |
| 9 | `p009_f15.png` | (b) Explanation |

## XGBoost: A Scalable Tree Boosting System (1603.02754)

Document id `52bc282c922a239134ee4d6f4367c58bf920a9bdd53acbb3b2aa3342e2bb7214` · 1 figure

| Page | File | Caption |
|---|---|---|
| 4 | `p004_f03.png` | Figure 3: Comparison of test AUC convergence on Higgs 10M dataset. The eps parameter corresponds to the acc… |

## Perceptual Losses for Real-Time Style Transfer and Super-Resolution (1603.08155)

Document id `6211443c2f4c92881759b850bee824b1660f53c61315d69e8f9486222bac2a87` · 1 figure

| Page | File | Caption |
|---|---|---|
| 9 | `p009_f05.png` | Fig. 5. Our style transfer networks and [10] minimize the same objective. We compare their objective values… |

## The Cityscapes Dataset for Semantic Urban Scene Understanding (1604.01685)

Document id `56fab90a6cf66d7f1bf3af7a6404ea89f55cf0754518d6e6a971e62f76b686e7` · 4 figures

| Page | File | Caption |
|---|---|---|
| 18 | `p018_f28.png` | (no caption) |
| 18 | `p018_f31.png` | (no caption) |
| 18 | `p018_f32.png` | (no caption) |
| 19 | `p019_f34.png` | (no caption) |

## V-Net: Fully Convolutional Neural Networks for Volumetric Medical Image Segmentation (1606.04797)

Document id `f3d7093a00e3a2db384e34c918d3ef86a74f9d3339c558a87cb4e9db443464d3` · 1 figure

| Page | File | Caption |
|---|---|---|
| 2 | `p002_f01.png` | Fig. 1. Slices from MRI volumes depicting prostate. This data is part of the PROMISE2012 challenge dataset… |

## node2vec: Scalable Feature Learning for Networks (1607.00653)

Document id `931089441454e76f93f0d4da5ae92a9731df87c0d7c7da80b00dde05f2ac220c` · 1 figure

| Page | File | Caption |
|---|---|---|
| 6 | `p006_f04.png` | Figure 3: Complementary visualizations of Les Misérables coappearance network generated by node2vec with la… |

## Layer Normalization (1607.06450)

Document id `c464f839fb8d59f7fde92f9b4caa67c2d1f2f196b88f93fb60502249df0aaef7` · 1 figure

| Page | File | Caption |
|---|---|---|
| 8 | `p008_f03.png` | Figure 3: Performance of skip-thought vectors with and without layer normalization on downstream tasks as a… |

## PointNet: Deep Learning on Point Sets for 3D Classification and Segmentation (1612.00593)

Document id `f13e3b3c744a3977155876e2d5dcd1d0cf83c22f98ce9cc11e0a2f5e37388b6a` · 1 figure

| Page | File | Caption |
|---|---|---|
| 16 | `p016_f20.png` | Figure 20. 2D embedding of learnt shape global features. We use t-SNE technique to visualize the learnt glo… |

## Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles (1612.01474)

Document id `185b16b3530d9c886b3c3811581a815b4dccee3b31b8705177ce8a3a31c259e5` · 1 figure

| Page | File | Caption |
|---|---|---|
| 9 | `p009_f05.png` | Figure 6: Accuracy vs Confidence curves: Networks trained on MNIST and tested on both MNIST test containing… |

## Mask R-CNN (1703.06870)

Document id `b595a882b763d55d933543131f32a2c4b6f41d0818d418ef46a2b66f946b67a8` · 1 figure

| Page | File | Caption |
|---|---|---|
| 4 | `p004_f04.png` | Figure 4. Head Architecture : We extend two existing Faster RCNN heads [19, 27]. Left/Right panels show the… |

## PointNet++: Deep Hierarchical Feature Learning on Point Sets in a Metric Space (1706.02413)

Document id `5cd120458cd481078aaf927f0bfed0ef646423e107f5cc2750b9c59f5b8e3795` · 1 figure

| Page | File | Caption |
|---|---|---|
| 7 | `p007_f07.png` | Figure 7: An example of nonrigid shape classification. |

## Proximal Policy Optimization Algorithms (1707.06347)

Document id `e78feadadbdbb0b601b3c2bcc81404722cd431a489b307545f9b7bea1e8c4f5b` · 1 figure

| Page | File | Caption |
|---|---|---|
| 4 | `p004_f02.png` | Figure 2: Surrogate objectives, as we interpolate between the initial policy parameter θ old , and the upda… |

## mixup: Beyond Empirical Risk Minimization (1710.09412)

Document id `d477fc9b3c5232669126d84406f17ae8261d19db8ebddfcb25ad995ca09b47e3` · 1 figure

| Page | File | Caption |
|---|---|---|
| 8 | `p008_f05.png` | Figure 5: Effect of mixup on stabilizing GAN training at iterations 10, 100, 1000, 10000, and 20000. |

## Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning with a Stochastic Actor (1801.01290)

Document id `5c33fae017d02f7025730f05198d4a6b103402822c8bbf48cbc5d8a0474c336a` · 1 figure

| Page | File | Caption |
|---|---|---|
| 8 | `p008_f03.png` | Figure 3. Sensitivity of soft actor-critic to selected hyperparameters on Ant-v1 task. (a) Evaluating the p… |

## The Unreasonable Effectiveness of Deep Features as a Perceptual Metric (1801.03924)

Document id `c43575003d83757725739ad87acfc4026d0d3129b27bee69fd1a4c362dc0db33` · 2 figures

| Page | File | Caption |
|---|---|---|
| 11 | `p011_f10.png` | Figure 8: Individual results (left) superresolution (right) frame interpolation |
| 11 | `p011_f11.png` | Figure 9: Individual results (left) video deblurring (right) colorization |

## Path Aggregation Network for Instance Segmentation (1803.01534)

Document id `a4e7defc9789dc38c162b05b9ced9f0e1bb845550e78f7cfecc64d7c4c804883` · 1 figure

| Page | File | Caption |
|---|---|---|
| 8 | `p008_f05.png` | Figure 5. Images in each row are visual results of our model on COCO test-dev , Cityscapes test and MVD tes… |

## Explainable Artificial Intelligence (XAI): Concepts, Taxonomies, Opportunities and Challenges toward Responsible AI (1910.10045)

Document id `02482b1fd9666ce16e6f488d7f0419307c795037e8d3e546082735b48b0c17ed` · 1 figure

| Page | File | Caption |
|---|---|---|
| 25 | `p025_f09.png` | (no caption) |

## Language Models are Few-Shot Learners (2005.14165)

Document id `97fd272f1fdfc18677462d0292f5fbf26ca86b4d1b485c2dba03269b643a0e83` · 2 figures

| Page | File | Caption |
|---|---|---|
| 4 | `p004_f02.png` | Figure 1.2: Larger models make increasingly efficient use of in-context information. Weshow in-context lear… |
| 64 | `p064_f25.png` | Figure H.2: Results for SAT task. |

## An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale (2010.11929)

Document id `8ce7b83971a14508ca711a27c875c9b6914c4f6767cf3150fb1ca6c07aa056d6` · 1 figure

| Page | File | Caption |
|---|---|---|
| 7 | `p007_f04.png` | (no caption) |

## Score-Based Generative Modeling through Stochastic Differential Equations (2011.13456)

Document id `b244b740e60628d01bc3d4b98d721c2343be1fb9b67ad22593c8555e66f4d4a6` · 1 figure

| Page | File | Caption |
|---|---|---|
| 8 | `p008_f05.png` | Figure 3: Probability flow ODE enables fast sampling with adaptive stepsizes as the numerical precision is… |

## Swin Transformer: Hierarchical Vision Transformer using Shifted Windows (2103.14030)

Document id `dfdc7631fe2a35bb5892080b9c0eeadc4432d55cf1856f84bc88802efa877a7c` · 1 figure

| Page | File | Caption |
|---|---|---|
| 4 | `p004_f03.png` | Figure 3. (a) The architecture of a Swin Transformer (Swin-T); (b) two successive Swin Transformer Blocks (… |

## Emerging Properties in Self-Supervised Vision Transformers (2104.14294)

Document id `aa464cfd59a428890190bea1065823a491a853478b4fb2a25f5eb44d442ce296` · 1 figure

| Page | File | Caption |
|---|---|---|
| 17 | `p017_f10.png` | (no caption) |

## Diffusion Models Beat GANs on Image Synthesis (2105.05233)

Document id `f3e66af0c1b698250d3f286dbd4641f91fce661d8af4f5b26ecdc427015b7ab6` · 4 figures

| Page | File | Caption |
|---|---|---|
| 22 | `p022_f11.png` | Figure 10a: DDIM latent reconstructions and interpolations on real images with no classifier guidance. |
| 23 | `p023_f12.png` | Figure 10b: DDIM latent reconstructions and interpolations on real images with classifier scale 1.0. |
| 23 | `p023_f13.png` | Figure 10c: DDIM latent reconstructions and interpolations on real images with classifier scale 2.5. |
| 24 | `p024_f15.png` | Figure 11: The effect of changing temperature for an ImageNet 128 × 128 model. |

## Evaluating Large Language Models Trained on Code (2107.03374)

Document id `ebae72ea0e8a5eb2ecbccdb985aec6cc1254a7c4d29e6d4de7866db1e66c4855` · 1 figure

| Page | File | Caption |
|---|---|---|
| 19 | `p019_f11.png` | Figure 13. Comparing the amount of bias and variance of two estimators of pass@ k . While the top expressio… |

## Training Verifiers to Solve Math Word Problems (2110.14168)

Document id `a52417d8fcd006de882e3b404850e2cc4246815828897c18c6ce6c7a448985a4` · 1 figure

| Page | File | Caption |
|---|---|---|
| 10 | `p010_f07.png` | (no caption) |

## Generative Adversarial Networks (2203.00667)

Document id `9f30cef56c7037772da19ea75681f779a34e085d13fa00bc0962aa1bcbbff723` · 1 figure

| Page | File | Caption |
|---|---|---|
| 21 | `p021_f17.png` | Fig. 17 Pipeline of Sphere GAN. The generator creates fake data from noise inputs. Real and fake data are f… |

## Training language models to follow instructions with human feedback (2203.02155)

Document id `c1984bb50a5b90fddb895fdc3a0f72e5bc977148c9f63ef6040cbe7a3e1f0d98` · 3 figures

| Page | File | Caption |
|---|---|---|
| 11 | `p011_f03.png` | Figure 3: Preference results of our models, measured by winrate against the 175B SFT model. Left: results o… |
| 13 | `p013_f06.png` | Figure 6: Results on the TruthfulQA dataset. Gray bars indicate ratings of truthfulness; colored bars indic… |
| 54 | `p054_f14.png` | Figure 31: Likert scores for each of our models |

## Hierarchical Text-Conditional Image Generation with CLIP Latents (2204.06125)

Document id `21e40300958a942545519c90f31bafdfe3c52b0f2fe988b9b2ac5750cf6c74ea` · 3 figures

| Page | File | Caption |
|---|---|---|
| 5 | `p005_f03.png` | Figure 3: Variations of an input image by encoding with CLIP and then decoding with a diffusion model. The… |
| 6 | `p006_f04.png` | Figure 4: Variations between two images by interpolating their CLIP image embedding and then decoding with… |
| 18 | `p018_f21.png` | (b) A high quality photo of Times Square. |

## GPT-4 Technical Report (2303.08774)

Document id `c33a66dadca2388d7b172d6293b00dc32b71110c6f38fafe0d41112e61be7774` · 2 figures

| Page | File | Caption |
|---|---|---|
| 10 | `p010_f07.png` | Figure 6. Performance of GPT-4 on nine internal adversarially-designed factuality evaluations. Accuracy is… |
| 98 | `p098_f28.png` | Figure 11: Results on IF evaluations across GPT3.5, GPT3.5-Turbo, GPT-4-launch |

## Segment Anything (2304.02643)

Document id `c6ca524e47200c3e542587ca76ac1dbc89cc67340f948c819250d16fdbd90cfb` · 8 figures

| Page | File | Caption |
|---|---|---|
| 4 | `p004_f03.png` | Figure 3: Each column shows 3 valid masks generated by SAM from a single ambiguous point prompt (green circ… |
| 29 | `p029_f21.png` | (no caption) |
| 29 | `p029_f24.png` | The second image on the top row shows the mask for the object in red. |
| 29 | `p029_f27.png` | Judging Mask Quality (2 of 3) |
| 30 | `p030_f33.png` | Example for 'Combine two unrelated things': The point indicates the lizard, but the mask covers both the li… |
| 30 | `p030_f36.png` | (no caption) |
| 30 | `p030_f41.png` | Example of a mask with a medium score (5-6): The mask clearly corresponds to the plate, but the boundary wi… |
| 30 | `p030_f46.png` | Example of a mask with a low-to-medium score (4-5): The object is identifiable and the edges are all correc… |

## Visual Instruction Tuning (2304.08485)

Document id `dc8bace378a282ea78caa9b5959306202fbfa3b8cedaf8a66541a9af18f4d3bf` · 1 figure

| Page | File | Caption |
|---|---|---|
| 6 | `p006_f03.png` | Source: https://www.barnorama.com/wp-content/uploads/2016/12/03-Confusing-Pictures.jpg |

## Direct Preference Optimization: Your Language Model is Secretly a Reward Model (2305.18290)

Document id `92cb3a2b71362acda98a789b03d88688fd33cf5fcf13f81d2b1de30ee7d3b67a` · 1 figure

| Page | File | Caption |
|---|---|---|
| 8 | `p008_f03.png` | Figure 3: Left. Win rates computed by GPT-4 for Anthropic-HH one-step dialogue; DPO is the only method that… |

## Orca: Progressive Learning from Complex Explanation Traces of GPT-4 (2306.02707)

Document id `f4b50e2de151fbf5f0ad9b7b790496152739d9caf10e2dcc7be6bf033ff36ffa` · 2 figures

| Page | File | Caption |
|---|---|---|
| 20 | `p020_f09.png` | Figure 11: Topical breakdown in performance of GPT-4, ChatGPT and Orca in the AGIEval benchmark on professi… |
| 24 | `p024_f13.png` | Figure 15: Failure rate (lower the better) of different models in instruction following for TruthfulQA. Vic… |

## Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (2306.05685)

Document id `1574982845157569b85c1214bfa9987000384d7a5e3b5fbdcc5a29afec59cb81` · 2 figures

| Page | File | Caption |
|---|---|---|
| 7 | `p007_f02.png` | Figure 3: Average win rate of six models under different judges on MT-bench. |
| 8 | `p008_f04.png` | (no caption) |

## Llama 2: Open Foundation and Fine-Tuned Chat Models (2307.09288)

Document id `1df284ce95f783002074bfe8f21d47c646b396ceb1736ea3ec0ea212fc070d91` · 2 figures

| Page | File | Caption |
|---|---|---|
| 3 | `p003_f02.png` | (no caption) |
| 48 | `p048_f25.png` | Figure 24: Multi-query variants enable higher throughput with larger batch sizes, and show similar latency… |

## Efficient Memory Management for Large Language Model Serving with PagedAttention (2309.06180)

Document id `55b3b324d779a67c59dac2519445e3b07c14e6ff5c656fadb47a3d7b5997469e` · 2 figures

| Page | File | Caption |
|---|---|---|
| 1 | `p001_f01.png` | Figure 1. Left: Memory layout when serving an LLM with 13B parameters on NVIDIA A100. The parameters (gray)… |
| 9 | `p009_f11.png` | Figure 11. Input and output length distributions of the (a) ShareGPT and (b) Alpaca datasets. |

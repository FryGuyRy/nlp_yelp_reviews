#!/bin/bash
TEXT_DIR=${HOME}/Desktop/Galvanize/Immersive/capstone/seq2seq/text
mkdir -p ${TEXT_DIR}
# cat ../nlp_yelp_reviews/txt_files/*.txt > ${TEXT_DIR}/train_text.txt
for f in ../nlp_yelp_reviews/txt_files/*.txt; do (cat "${f}"; echo 笑) >> ${TEXT_DIR}/train_text.txt; done
# cat ../nlp_yelp_reviews/txt_label_files/*.txt > ${TEXT_DIR}/train_label.txt
for f in ../nlp_yelp_reviews/txt_label_files/*.txt; do (cat "${f}"; echo 笑) >> ${TEXT_DIR}/train_label.txt; done
wc -l < ${TEXT_DIR}/train_label.txt


head -1 ${TEXT_DIR}/train_text.txt > data_test.20.txt
head -1 ${TEXT_DIR}/train_text.txt > data_train.80.txt
tail -n+2 ${TEXT_DIR}/train_text.txt | awk '{if( NR % 10 <= 1){ print $0 >> "data_test.20.txt"} else {print $0 >> "data_train.80.txt"}}'
wc -l < data_test.20.txt
wc -l < data_train.80.txt


head -1 ${TEXT_DIR}/train_label.txt > data_test.labels.20.txt
head -1 ${TEXT_DIR}/train_label.txt > data_train.labels.80.txt
tail -n+2 ${TEXT_DIR}/train_label.txt | awk '{if( NR % 10 <= 1){ print $0 >> "data_test.labels.20.txt"} else {print $0 >> "data_train.labels.80.txt"}}'
wc -l < data_test.labels.20.txt
wc -l < data_train.labels.80.txt

./bin/tools/generate_vocab.py \
--max_vocab_size 50000 \
< data_train.80.txt > \
${TEXT_DIR}/vocab_train_text.txt

./bin/tools/generate_vocab.py \
--delimiter "" \
--max_vocab_size 50000 \
< data_train.labels.80.txt > \
${TEXT_DIR}/vocab_train_label.txt

VOCAB_SOURCE=${TEXT_DIR}/vocab_train_text.txt
VOCAB_TARGET=${TEXT_DIR}/vocab_train_label.txt
TRAIN_SOURCES=data_train.80.txt
TRAIN_TARGETS=data_train.labels.80.txt
DEV_SOURCES=data_test.20.txt
DEV_TARGETS=data_test.labels.20.txt

# DEV_TARGETS_REF=${TEXT_DIR}/train_label.txt
TRAIN_STEPS=500000

MODEL_DIR=${HOME}/Desktop/Galvanize/Immersive/capstone/seq2seq/max_models
PRED_DIR=${MODEL_DIR}/pred


mkdir -p $MODEL_DIR
python -m bin.train \
  --config_paths="
      ./example_configs/nmt_small.yml,
      ./example_configs/train_seq2seq.yml,
      ./example_configs/text_metrics_sp.yml" \
  --model_params "
      vocab_source: $VOCAB_SOURCE
      vocab_target: $VOCAB_TARGET" \
  --input_pipeline_train "
    class: ParallelTextInputPipeline
    params:
      source_files:
        - $TRAIN_SOURCES
      target_files:
        - $TRAIN_TARGETS" \
  --input_pipeline_dev "
    class: ParallelTextInputPipeline
    params:
       source_files:
        - $DEV_SOURCES
       target_files:
        - $DEV_TARGETS" \
  --batch_size 32 \
  --train_steps $TRAIN_STEPS \
  --output_dir $MODEL_DIR

mkdir -p ${PRED_DIR}
# python -m bin.infer \
#   --tasks "
#     - class: DecodeText" \
#   --model_dir $MODEL_DIR \
#   --input_pipeline "
#     class: ParallelTextInputPipeline
#     params:
#       source_files:
#         - $DEV_SOURCES" \
#   > ${PRED_DIR}/predictions.txt

python -m bin.infer \
  --tasks "
    - class: DecodeText
    - class: DumpBeams
      params:
        file: ${PRED_DIR}/beams.npz" \
  --model_dir $MODEL_DIR \
  --model_params "
    inference.beam_search.beam_width: 2" \
  --input_pipeline "
    class: ParallelTextInputPipeline
    params:
      source_files:
        - $DEV_SOURCES" \
  > ${PRED_DIR}/predictions.txt

  # python -m bin.tools.generate_beam_viz  \
  # -o ${TMPDIR:-/tmp}/beam_visualizations \
  # -d ${TMPDIR:-/tmp}/beams.npz \
  # -v ${TEXT_DIR}/vocab_train_text.txt

  ./bin/tools/multi-bleu.perl ${DEV_TARGETS} < ${PRED_DIR}/predictions.txt

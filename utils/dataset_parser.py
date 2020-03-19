import pandas as pd
import os
import random
import numpy as np


def generate_train_valid_test(dataset_dir,splitfiles,left_prefix,right_prefix,drop_lrid=True):
    df_tableA = pd.read_csv(os.path.join(dataset_dir,'tableA.csv'))
    df_tableB = pd.read_csv(os.path.join(dataset_dir,'tableB.csv'))
    datasets_ids = []
    for splitname in splitfiles:
        datasets_ids.append(pd.read_csv(os.path.join(dataset_dir,splitname)))
    left_columns = []
    right_columns = []
    for lcol,rcol in zip(list(df_tableA),list(df_tableB)):
        left_columns.append(left_prefix+lcol)
        right_columns.append(right_prefix+rcol)
    df_tableA.columns = left_columns
    df_tableB.columns = right_columns
    datasets = []
    #P sta per parziale
    for dataset_id in datasets_ids:
        pdata = pd.merge(dataset_id,df_tableA, how='inner',left_on='ltable_id',right_on=left_prefix+'id')
        dataset = pd.merge(pdata,df_tableB,how='inner',left_on='rtable_id',right_on=right_prefix+'id')
        datasets.append(dataset)

    train_lenght = datasets[0].shape[0]
    valid_lenght = datasets[1].shape[0]
    test_lenght = datasets[2].shape[0]

    train_ids = np.arange(0,train_lenght)
    valid_ids = np.arange(train_lenght,train_lenght+valid_lenght)
    test_ids = np.arange(train_lenght+valid_lenght,train_lenght+valid_lenght+test_lenght)
    if drop_lrid:
        train = datasets[0].drop(['ltable_id','rtable_id'],axis=1)
        valid = datasets[1].drop(['ltable_id','rtable_id'],axis=1)
        test = datasets[2].drop(['ltable_id','rtable_id'],axis=1)
    else:
        train = datasets[0]
        valid = datasets[1]
        test = datasets[2]
    train['id'] = train_ids
    valid['id'] = valid_ids
    test['id'] = test_ids
    return train,valid,test



def generateDataset(dataset_dir,source1,source2,pairs_ids,lprefix,rprefix):
    source1_df = pd.read_csv(os.path.join(dataset_dir,source1),dtype=str)
    source2_df = pd.read_csv(os.path.join(dataset_dir,source2),dtype=str)
    pairs_ids_df = pd.read_csv(os.path.join(dataset_dir,pairs_ids),dtype=str)
    ##to avoid duplicate columns
    pairs_ids_df.columns = ['id1','id2','label']
    lcolumns,rcolumns = ([],[])
    for lcol,rcol in zip(list(source1_df),list(source2_df)):
        lcolumns.append(lprefix+lcol)
        rcolumns.append(rprefix+rcol)
    source1_df.columns = lcolumns
    source2_df.columns = rcolumns
    pdata = pd.merge(pairs_ids_df,source1_df, how='inner',left_on='id1',right_on=lprefix+'id')
    dataset = pd.merge(pdata,source2_df,how='inner',left_on='id2',right_on=rprefix+'id')
    dataset['id'] = dataset[lprefix+'id']+"#"+dataset[rprefix+'id']
    dataset = dataset.drop(['id1','id2',lprefix+'id',rprefix+'id'],axis=1)
    return dataset


def get_pos_neg_datasets(splits):
    allSamples = pd.concat(splits,ignore_index=True)
    positives_df = allSamples[allSamples.label==1]
    negatives_df = allSamples[allSamples.label==0]
    return positives_df,negatives_df


def generate_unlabeled(dataset_dir,unlabeled_filename,lprefix='ltable_',rprefix='rtable_'):
    df_tableA = pd.read_csv(os.path.join(dataset_dir,'tableA.csv'))
    df_tableB = pd.read_csv(os.path.join(dataset_dir,'tableB.csv'))
    unlabeled_ids = pd.read_csv(os.path.join(dataset_dir,unlabeled_filename))
    left_columns = list(map(lambda s:lprefix+s,list(df_tableA)))
    right_columns = list(map(lambda s:rprefix+s,list(df_tableB)))
    df_tableA.columns = left_columns
    df_tableB.columns = right_columns

    #P sta per parziale
    punlabeled = pd.merge(unlabeled_ids,df_tableA, how='inner',left_on=lprefix+'id',right_on='ltable_id')
    unlabeled_df = pd.merge(punlabeled,df_tableB,how='inner',left_on='rtable_id',right_on=rprefix+'id')

    unlabeled_df = unlabeled_df.drop(['ltable_id','rtable_id'],axis=1)
    unlabeled_df['id'] = np.arange(unlabeled_df.shape[0])
    return unlabeled_df


def getFullDataset(splits):
    return pd.concat(splits,ignore_index=True)



def dropTokensInColumns(df,attributes,tokensL):
    df_copy = df.copy()
    for attr in attributes:
        df_copy[attr] = df_copy[attr].apply(lambda r:dropTokens(r,tokensL))
    return df_copy


def dropTokens(attr,tokensL):
    attr_tokens = list(map(lambda t:t.lower(),attr.split()))
    filtered_tokens = []
    for tok in attr_tokens:
        if tok not in tokensL:
            filtered_tokens.append(tok)
    return " ".join(filtered_tokens)


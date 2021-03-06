import pandas as pd
import numpy as np
from model_validation import ModelValidation
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import make_scorer, r2_score
from sklearn.svm import LinearSVR
from sklearn.preprocessing import StandardScaler


# Load data
df = pd.read_csv("data/Series3_6.15.17_padel.csv", index_col=0)
# Eliminate features without variance
df = df.loc[:, (df.std() > 0).values]
# Seperate Series 3 test when IC50 is null
test_index = df.IC50.isnull()
test_df = df.loc[test_index]
df = df.loc[~test_index]
# Remove columns with missing data
df = df.dropna(axis=1)
# Transform discrete with one-hot-encoding
int_cols = df.columns[df.dtypes == 'int64']
float_cols = df.columns[df.dtypes == 'float64']
one_hot_df = pd.get_dummies(df[int_cols].astype('O'))
df = pd.merge(df[float_cols], one_hot_df, left_index=True, right_index=True)
# Split x, y
y_data = df.pop("IC50")
x_data = df.copy()

# Ensure no (+/-) inf or nan due to improper transformation
x_data.replace([np.inf, -np.inf], np.nan, inplace=True)
assert not sum(x_data.isna().sum()), "Unexpected nulls found"

# Perform feature engineering on float columns
for feat in x_data.columns[x_data.dtypes == 'float64']:
    feature_df = x_data.loc[:, feat]
    if feature_df.min() > 0:  # Avoid 0 or negative
        x_data.loc[:, feat + "_log"] = feature_df.apply(np.log)  # log
        x_data.loc[:, feat + "_log2"] = feature_df.apply(np.log2)  # log2
        x_data.loc[:, feat + "_log10"] = feature_df.apply(np.log10)  # log10
        x_data.loc[:, feat + "_cubert"] = feature_df.apply(
            lambda x: np.power(x, 1 / 3))  # cube root
        x_data.loc[:, feat + "_sqrt"] = feature_df.apply(np.sqrt)  # square root
    # Avoid extremely large values, keep around 1M max
    if feature_df.max() < 13:
        x_data.loc[:, feat + "_exp"] = feature_df.apply(np.exp)  # exp
    if feature_df.max() < 20:
        x_data.loc[:, feat + "_exp2"] = feature_df.apply(np.exp2)  # exp2
    if feature_df.max() < 100:
        x_data.loc[:, feat + "_cube"] = feature_df.apply(
            lambda x: np.power(x, 3))  # cube
    if feature_df.max() < 1000:
        x_data.loc[:, feat + "_sq"] = feature_df.apply(np.square)  # square

# Normalize
x_scaler = StandardScaler()
y_scaler = StandardScaler()

x_data.loc[:, :] = x_scaler.fit_transform(x_data)
y_data.loc[:] = np.squeeze(y_scaler.fit_transform(y_data.values.reshape(-1, 1)))

# Remove highly correlated features, group by correlation and select 1 from each group
best_corr_thresh = .97
# best_r2_score = .18796

# Use all features except those with very high correlations. Those can be treated as identical.


corr_threshold = best_corr_thresh
corr_matrix = x_data.corr()
corr_matrix.loc[:, :] = np.tril(corr_matrix, k=-1)  # borrowed from Karl D's answer

already_in = set()
corr_result = []
for col in corr_matrix:
    correlated = corr_matrix[col][np.abs(corr_matrix[col]) > corr_threshold].index.tolist()
    if correlated and col not in already_in:
        already_in.update(set(correlated))
        correlated.append(col)
        corr_result.append(correlated)
    elif col not in already_in:
        already_in.update(set([col]))
        corr_result.append([col])


all_feats = set(list(x_data.columns))
selected_feats = set([corr_feats[0] for corr_feats in corr_result])
removed_feats = all_feats - selected_feats

x_data.loc[:, selected_feats]

# For each column, count the number in the group (col, count)
corr_group_counts = dict([(feat, len(corr_feats)) for corr_feats in corr_result for feat in corr_feats])

# Selecting for removal

# Benchmark for Lasso regression
model = LinearSVR(random_state=0)
params = {"C": np.arange(.1, 1.1, .1)}
# rskf = RepeatedStratifiedKFold(n_splits=10, n_repeats=10, random_state=0)  # Classification only
grid = GridSearchCV(model, param_grid=params, scoring=make_scorer(r2_score, greater_is_better=True), cv=10, n_jobs=7)

grid.fit(x_data.loc[:, selected_feats], y_data)

validate = ModelValidation()
results = validate.score_regressor(x_data.loc[:, selected_feats], y_data,
                                   grid.best_estimator_, pos_split=y_scaler.transform([[2.1]]))
round_r2_score = np.mean(results["r2_score"])

# Best R2 Score: .1879, corr_threshold = .91

# Using backward stepwise selection, remove a max of 5% each iteration (tune)
# Favor the features that are part of larger correlated group when tie

# Rank features by coef_
[feat for coef, feat in sorted(zip(abs(grid.best_estimator_.coef_), selected_feats))]
# TODO Start here!!!
# TODO determine best way to select features for removal. If the starting features are less correlated then
# todo it'll be easier to keep the model stable when removing features. Try keeping it simple and tune the threshold
# So just remove the first 1-5% or so...


# Starting with groups of perfect correlations, select one from each group to represent that dimension
# Create loop that selects features for removal by number of correlated features in a group with a decreasing
# threshold and also by coefficient (primary sort)

# Build a set for removal





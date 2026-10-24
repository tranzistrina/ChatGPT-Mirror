<template>
  <div>
    <t-card class="list-card-container">
      <t-row justify="space-between">
        <div class="left-operation-container">
          <t-button @click="handleShowDialog()">{{ $t('mirror.k65b0_589e') }}</t-button>
        </div>
      </t-row>

      <t-table
        :data="tableData"
        :columns="columns"
        row-key="car_name"
        :loading="tableLoading"
        bordered
        hover
        :pagination="pagination"
        @page-change="rehandlePageChange"
      >
        <template #gpt_account_name_list="{ row }">
          <t-popup trigger="hover" :show-arrow="true" placement="right">
            <template #content>
              <div>
                <t-space direction="vertical">
                  <t-tag v-for="item in row.gpt_account_name_list" :key="item" max-width="200"> {{ item }} </t-tag>
                </t-space>
              </div>
            </template>

            <t-link variant="outline"> ChatGPT 账号 {{ row.gpt_account_name_list.length }} 个 </t-link>
          </t-popup>
          <!-- <t-space style="display: flex; flex-wrap: wrap; max-width: 100%; overflow: hidden">
            <t-tag v-for="item in row.gpt_account_name_list" :key="item" max-width="80"> {{ item }} </t-tag>
          </t-space> -->
        </template>

        <template #created_time="{ row }">
          {{ TimestampToDate(row.created_time * 1000) }}
        </template>

        <template #op="slotProps">
          <t-space>
            <t-link theme="primary" @click="handleEdit(slotProps.row)">{{ $t('mirror.k7f16_8f91') }}</t-link>
            <t-link theme="danger" @click="handleClickDelete(slotProps.row)">{{ $t('mirror.k5220_9664') }}</t-link>
          </t-space>
        </template>
      </t-table>

      <!-- 添加/编辑 用户 dialog -->
      <t-dialog v-model:visible="showDialog" :on-confirm="handleConfirm" :title="$t('mirror.k65b0_589e_20_7528_6237')" width="800px">
        <t-form
          ref="addFormRef"
          v-loading="loading"
          :rules="rules"
          :data="newGptCar"
          :label-width="120"
          @submit="handleAdd"
        >
          <t-form-item :label="$t('mirror.k53f7_6c60_540d_79f0')" name="car_name">
            <t-input v-model="newGptCar.car_name" :disabled="actionType == 'edit'" style="width: 240px"></t-input>
          </t-form-item>

          <t-form-item label="选择 ChatGPT" name="gptcar_list">
            <t-space style="width: 100%">
              <t-select
                v-model="newGptCar.gpt_account_list"
                multiple
                placeholder="Select"
                filterable
                :min-collapsed-num="1"
              >
                <t-option
                  v-for="item in gptAccountList"
                  :key="item.id"
                  :label="`${item.plan_type} / ${item.chatgpt_username}`"
                  :value="item.id"
                />
              </t-select>
            </t-space>
          </t-form-item>

          <t-form-item :label="$t('mirror.k5907_6ce8')" name="remark">
            <t-textarea v-model="newGptCar.remark"></t-textarea>
          </t-form-item>
        </t-form>
      </t-dialog>

      <!-- 确认删除 dialog -->
      <t-dialog
        v-model:visible="dialogVisibleDelete"
        :header="$t('mirror.k786e_8ba4_5220_9664_8be5_20_53f7_6c60_20_5417')"
        width="600"
        :on-confirm="handleDelete"
      >
      </t-dialog>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { t } from '@/locales';
import { FormProps, MessagePlugin, TableProps } from 'tdesign-vue-next';
import { onMounted, ref } from 'vue';

import RequestApi from '@/api/request';
import { TimestampToDate } from '@/utils/date';

onMounted(async () => {
  await getChatCarList();
});

const GptCarUrl = '/0x/chatgpt/car';
const tableLoading = ref(false);
const loading = ref(false);

const showDialog = ref(false);
const actionType = ref('add');
const gptAccountList = ref([]);
const addFormRef = ref();
const gptcaridDelete = ref();
const dialogVisibleDelete = ref(false);

const GptCarUri = '/0x/chatgpt/car';

const tableData = ref<TableData[]>([]);
const columns: TableProps['columns'] = [
  { colKey: 'car_name', title: t('mirror.k53f7_6c60_540d_79f0'), width: 220 },
  { colKey: 'gpt_account_name_list', title: 'gpt 账号', width: 200 },
  { colKey: 'created_time', title: t('mirror.k521b_5efa_65f6_95f4'), width: 200 },

  { colKey: 'remark', title: t('mirror.k5907_6ce8'), width: 220 },

  { width: 200, colKey: 'op', title: t('mirror.k64cd_4f5c') },
];

const pagination = {
  defaultPageSize: 20,
  total: 0,
  defaultCurrent: 1,
};

const rehandlePageChange = (curr: any) => {
  pagination.defaultCurrent = curr.current;
  pagination.defaultPageSize = curr.pageSize;
  getChatCarList();
};

interface GptCarForm {
  remark: string;
  car_name: string;
  gpt_account_list: any[];
}

interface TableData {
  remark: string;
  car_name: string;
  gpt_account_list: any[];
}

const defaultGptCar = {
  remark: '',
  car_name: '',
  gpt_account_list: [] as any[],
};

const rules: FormProps['rules'] = {
  car_name: [{ required: true, message: 'Please input car_name', trigger: 'blur' }],
  gpt_account_list: [{ required: true, message: 'Please input gpt_account_list', trigger: 'blur' }],
};

const newGptCar = ref<GptCarForm>({ ...defaultGptCar });

const handleConfirm = async () => {
  if (addFormRef.value) {
    addFormRef.value.submit();
  }
};

const getChatCarList = async () => {
  // 发送请求获取 gptcar 列表
  tableLoading.value = true;
  const params: any = {
    page: pagination.defaultCurrent,
    page_size: pagination.defaultPageSize,
  };

  const queryString = new URLSearchParams(params).toString();
  const response = await RequestApi(`${GptCarUrl}?${queryString}`);

  const data = await response.json();
  // console.log('results', data.results);
  tableData.value = data.results;
  pagination.total = data.count;
  tableLoading.value = false;
};

const handleEdit = async (user: GptCarForm) => {
  newGptCar.value = { ...user };
  await getGptAccountEnum();
  showDialog.value = true;
  actionType.value = 'edit';
};

const handleClickDelete = (row: any) => {
  gptcaridDelete.value = row.id;
  dialogVisibleDelete.value = true;
};

const getGptAccountEnum = async () => {
  // 发送请求获取 号池 列表
  const response = await RequestApi('/0x/chatgpt/enum');
  const data = await response.json();
  gptAccountList.value = data.data;
};

const handleShowDialog = async () => {
  await getGptAccountEnum();
  showDialog.value = true;
  actionType.value = 'add';
  newGptCar.value = { ...defaultGptCar };
};

const addgptCar = async () => {
  loading.value = true;
  const response = await RequestApi(GptCarUri, 'POST', newGptCar.value);
  loading.value = false;

  if (response.status !== 200) {
    const data = await response.json();
    MessagePlugin.error(JSON.stringify(Object.values(data)[0]));
  } else {
    await getChatCarList();
    newGptCar.value = defaultGptCar;
    showDialog.value = false;
    MessagePlugin.success(t('mirror.k65b0_589e_6210_529f'));
  }
};

const handleAdd: FormProps['onSubmit'] = async ({ validateResult, firstError }) => {
  console.log('validateResult', validateResult);
  if (validateResult === true) {
    addgptCar();
  } else {
    console.error('表单引用未定义', firstError);
  }
};

const handleDelete = async () => {
  const response = await RequestApi(GptCarUri, 'DELETE', { ids: [gptcaridDelete.value] });

  const data = await response.json();
  dialogVisibleDelete.value = false;
  gptcaridDelete.value = null;

  if (response.status !== 200) {
    MessagePlugin.error(JSON.stringify(Object.values(data)[0]));
  } else {
    await getChatCarList();
    MessagePlugin.success(t('mirror.k5220_9664_6210_529f'));
  }
};
</script>

<style lang="less" scoped>
.left-operation-container {
  padding: 6px 0;
  margin-bottom: 16px;

  .selected-count {
    display: inline-block;
    margin-left: 8px;
    color: var(--td-text-color-secondary);
  }
}
</style>
